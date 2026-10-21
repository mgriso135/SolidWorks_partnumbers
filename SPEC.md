# PartCode — Product Specification

**Version:** 1.0 (MVP)
**Date:** 2026-10-20
**Companion documents:** `REQUIREMENTS.md` (source research), `PLAN.md` (delivery plan)

---

## 1. What we are building

**PartCode** is a cloud service that centralizes a company's item/document coding rules and makes them available inside the tools engineers already use — SolidWorks, SolidWorks PDM, ERP, and Office.

It is **not** a PDM or an ERP. It is the authoritative **coding layer** that sits between them:

- PDM remains the source of truth for CAD files and document metadata.
- ERP remains the source of truth for released items and BOMs.
- PartCode owns the **rules**, generates **unique, standards-compliant codes**, and supplies **consistent metadata** to both sides.

### 1.1 Problem

Companies with PDM + ERP commonly suffer from:

- Manual code entry, re-keying, and inconsistent formats.
- Duplicate codes across CAD, PDM, and ERP.
- Codes that encode meaning (type/material/size) but drift over time.
- Coding rules trapped in one department or in ERP customization.
- New hires and suppliers not knowing the conventions.
- No audit trail for who created which code and why.

### 1.2 Product principles

1. **Rules, not hard-coded logic.** Administrators change numbering without a software release.
2. **Generate where people work.** A code should arrive in the PDM data card, not in a separate portal.
3. **One definition, many consumers.** CAD, PDM, ERP, and Office read the same rule set.
4. **Fail closed.** Never write a partial or non-compliant code.
5. **Cloud core, thin connectors.** Browser UI + REST API; native connectors as thin clients.

---

## 2. Users and roles

| Role | Capabilities |
|---|---|
| `admin` | Everything: rules, users, API keys, items, audit, settings. |
| `editor` | Create/edit/archive rules, generate and void codes, view items/audit. |
| `viewer` | Generate and search codes, view rules (read-only). |
| `service` (API key) | Machine-to-machine generation and lookup from PDM/ERP connectors. |

Multi-tenancy: every record is scoped by `tenant_id`. The MVP ships with one seeded tenant; the schema and queries enforce isolation.

---

## 3. Core use cases

### UC-1 — Engineer creates a new part
1. Engineer opens PartCode from the PDM add-in (or the web UI).
2. Selects the active rule for the document type.
3. Fills guided fields (family, material, size, description).
4. PartCode previews the code and validates every field.
5. Engineer commits; PartCode atomically reserves the progressive number.
6. The code and attributes are written to the PDM data card and checked in.

### UC-2 — Administrator defines a rule
1. Admin creates a rule with a name, document type, and ordered segments.
2. Segments can be literal, separator, list, text, date, counter, or checksum.
3. Admin previews the format with sample values and activates the rule.
4. Every edit creates a new immutable version; the previous version is archived.
5. Changes are recorded in the audit log.

### UC-3 — Duplicate prevention
1. Connector submits a candidate code (generated or manual).
2. PartCode checks its code registry and, optionally, forwards a lookup to the ERP.
3. On collision, the request is rejected with a structured conflict response.

### UC-4 — PDM → ERP handoff
1. PDM add-in reserves code `PRT-MEC-00042` with attributes.
2. The PDM↔ERP integration reads the code and attributes by `external_ref`.
3. ERP creates/reconciles the item; PartCode records the handoff in the audit log.

### UC-5 — Auditing
1. Admin filters the audit log by actor, action, and date.
2. Every generation stores the rule version and input payload, making the code reproducible.

---

## 4. Functional scope (MVP)

### 4.1 Rule engine
- JSON rule definition with ordered segments:
  - `literal`, `separator`, `list` (controlled options), `text` (regex/length), `date` (strftime), `counter` (padding/start/step/scope), `checksum` (`mod97`, `luhn`).
- Validation: required fields, allowed options, regex, max length, final code format.
- Versioning: immutable versions keyed by `rule_key` + `version`; one active version per key.
- Preview without consuming counter values.
- Atomic, concurrency-safe counter reservation.
- Scoped counters (`rule` or `per_value` using selected segment keys).

### 4.2 Codes and items
- Commit a code with arbitrary metadata JSON (`material`, `description`, `size`, …).
- Unique `(tenant_id, code)` constraint with retry on collision.
- Status: `reserved`, `committed`, `void`.
- External reference for PDM/ERP correlation.
- Search and filtering.

### 4.3 Integrations
- REST API for all operations.
- API-key authentication for machine clients (`X-API-Key`).
- PDM connector simulation endpoint: reserve/lookup/validate.
- ERP lookup interface with a local stub (production adapter to be implemented per ERP).
- Signed-in web UI for humans.

### 4.4 Administration
- User management (create, list, deactivate, role change).
- API key management (create, list, revoke; secret shown once).
- Audit log with filters.
- Dashboard metrics.

### 4.5 Explicitly out of scope for the MVP
- A native SolidWorks PDM add-in was outside the MVP build. It is now implemented as phase 1.2 in `pdm-connector/`: a .NET Framework 4.8 COM add-in plus installer. Live-vault validation still requires Windows and SOLIDWORKS PDM Professional.
- Real ERP adapters (SAP, Teamcenter, etc.).
- Full BOM management, workflow engine, supplier portal.
- Billing, email notifications, SSO.
- Horizontal scaling and HA deployment automation.

---

## 5. Rule definition format

```json
{
  "segments": [
    { "type": "literal", "value": "PRT" },
    { "type": "separator", "value": "-" },
    {
      "type": "list", "key": "family", "label": "Family", "required": true,
      "options": [
        { "value": "MEC", "label": "Mechanical" },
        { "value": "ELE", "label": "Electrical" },
        { "value": "PNE", "label": "Pneumatic" }
      ]
    },
    { "type": "separator", "value": "-" },
    {
      "type": "counter", "key": "seq", "padding": 5, "start": 1, "step": 1,
      "scope": "per_value", "scope_keys": ["family"]
    }
  ],
  "max_length": 32,
  "case": "upper"
}
```

Rules may also include `date` (`{"type":"date","format":"%y"}`), `text` (`min`/`max`/`regex`), and `checksum` (`{"type":"checksum","algorithm":"mod97"}`).

### 5.1 Generation contract

```json
POST /api/generate
{
  "rule_key": "mechanical-part",
  "values": { "family": "MEC", "description": "Bracket", "material": "S355" },
  "source": "pdm",
  "external_ref": "vault://Projects/BR-100/Bracket.SLDPRT",
  "metadata": { "material": "S355" }
}
```

```json
{
  "code": "PRT-MEC-00001",
  "rule_key": "mechanical-part",
  "rule_version": 3,
  "item_id": "…",
  "segments": [
    { "key": null, "value": "PRT", "type": "literal" },
    { "key": "family", "value": "MEC", "type": "list" },
    { "key": "seq", "value": "00001", "type": "counter" }
  ],
  "status": "reserved",
  "created_at": "2026-10-20T10:00:00Z"
}
```

Errors are structured: `{ "detail": { "code": "INVALID_INPUT", "message": "…", "fields": {...} } }`.

---

## 6. Architecture

```
┌──────────────────────┐      ┌──────────────────────┐
│  React SPA (Vite)    │      │ SolidWorks PDM add-in │
│  Rules / Generate    │      │ (future, Windows)     │
└──────────┬───────────┘      └──────────┬───────────┘
           │ HTTPS + JWT                 │ HTTPS + X-API-Key
           ▼                             ▼
┌─────────────────────────────────────────────────────┐
│                   FastAPI application               │
│  auth │ rules │ generation │ items │ audit │ admin  │
│                 Rule engine + validator             │
└──────────────────────────┬──────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────┐
│ SQLAlchemy ORM — SQLite (dev) / PostgreSQL (prod)   │
│ tenants, users, rules, counters, items, audit, keys │
└─────────────────────────────────────────────────────┘
                           │ adapter interface
                           ▼
                    ERP lookup stub
```

### 6.1 Technology choices

| Layer | Choice | Why |
|---|---|---|
| API | Python 3.13 + FastAPI | Fast to build, typed schemas, OpenAPI for free. |
| ORM | SQLAlchemy 2 + Alembic | Portable SQLite → PostgreSQL with versioned migrations. |
| DB | SQLite (dev), PostgreSQL 17 (prod) | Zero-setup local; Compose deployment path. |
| Auth | JWT (HS256) + scrypt password hashing (stdlib) | No external auth dependency in the MVP. |
| Frontend | React 19 + TypeScript + Vite | Small, fast, type-safe SPA. |
| Tests | pytest + httpx | API-level coverage of the critical paths. |
| Lint | Ruff | Fast Python linting. |

### 6.2 Key data model

- `tenants(id, name, slug, created_at)`
- `users(id, tenant_id, email, password_hash, role, active, created_at)`
- `rules(id, tenant_id, key, name, description, document_type, version, status, definition_json, created_by, created_at)`
  - unique `(tenant_id, key, version)`, index `(tenant_id, key, status)`
- `counters(id, tenant_id, rule_key, scope_key, value, updated_at)`
  - unique `(tenant_id, rule_key, scope_key)`
- `items(id, tenant_id, code, rule_id, rule_key, rule_version, status, source, payload_json, external_ref, created_by, created_at, voided_at)`
  - unique `(tenant_id, code)`
- `api_keys(id, tenant_id, name, prefix, key_hash, last_used_at, revoked_at, created_at)`
- `audit_log(id, tenant_id, actor_id, actor_type, action, entity_type, entity_id, details_json, ip, created_at)`

### 6.3 Concurrency and uniqueness

Counter reservation uses a single atomic upsert:

```sql
INSERT INTO counters (tenant_id, rule_key, scope_key, value, updated_at)
VALUES (:tenant, :rule, :scope, :start, :now)
ON CONFLICT (tenant_id, rule_key, scope_key)
DO UPDATE SET value = counters.value + :step, updated_at = :now
RETURNING value;
```

The unique constraint on `(tenant_id, code)` is the final guard; collisions retry with the next counter value (bounded).

---

## 7. Security

- Passwords hashed with scrypt (N=2^14, r=8, p=1) and per-user salt.
- JWT bearer tokens, 12-hour expiry, `sub` = user id, `tid` = tenant id.
- API keys: 32-byte random secret, SHA-256 hash stored; only prefix and last-used timestamp are visible after creation.
- Tenant scoping enforced in every query, not only in handlers.
- CORS restricted to configured frontend origins.
- All writes audited with actor, IP, and payload summary.
- Secrets come from environment variables; nothing sensitive is committed.

---

## 8. PDM / ERP integration contract

### 8.1 PDM connector (Windows add-in, phase 1.2)
1. `GET /api/rules?document_type=part&status=active` — load usable rules.
2. `POST /api/generate/preview` — show the candidate code in the data card.
3. `POST /api/generate` — reserve the code at check-in.
4. `GET /api/items/lookup?code=…` — validate an existing code.
5. On failure, block check-in and surface the structured error.

The connector never computes codes locally; it only renders and submits.

The phase 1.2 implementation reads data-card variables, loads active rules, previews/reserves through the API-key endpoints, and writes the returned code to a configurable PDM variable. See `pdm-connector/README.md` for the build, installer, DPAPI key handling, and the remaining live-vault validation steps.

### 8.2 ERP adapter
- MVP ships an interface plus an in-memory/stub adapter.
- A production adapter must implement `lookup(code)` and `exists(code)`; optional `propose_item(payload)`.
- ERP remains authoritative; PartCode never silently overwrites ERP data.

### 8.3 API key flow
```
POST /api/admin/api-keys        → { "key": "pk_live_…" }  (shown once)
GET  /api/integrations/pdm/…    with header `X-API-Key: pk_live_…`
```

---

## 9. Success criteria for the MVP

1. A user can log in and generate a valid, unique code from a seeded rule in under 30 seconds.
2. Preview never consumes a counter; commit increments exactly once.
3. Two concurrent commits on the same rule never return the same code.
4. Editing a rule produces a new version and leaves historical items reproducible.
5. A machine client with an API key can generate and look up codes.
6. Invalid input is rejected with actionable field-level errors.
7. The frontend builds with zero TypeScript errors and the backend test suite passes.
8. The full flow is demonstrable end-to-end locally with documented commands.

---

## 10. Roadmap beyond the MVP

Phase 1.1 (PostgreSQL, Docker Compose, Alembic) is deployed and phase 1.2 (PDM add-in, shared client, installer) is implemented in this repository. The PDM add-in is compile-verified against the PDM 2024 interop and still requires a Windows pilot against a real vault. Phase 1.3 is the next planned tranche: web-side item linkage so codes can be attached to PDM/ERP references without deploying the add-in.

| Phase | Scope | Status |
|---|---|---|
| 1.1 | PostgreSQL deployment, Docker Compose, migrations (Alembic). | Complete; deployed on Debian 13 with Docker and existing PostgreSQL |
| 1.2 | Real SolidWorks PDM add-in (.NET, COM) + installer. | Implemented; build-verified, live vault pending |
| 1.3 | Item linkage and metadata: external references, notes, edit-after-generation. | Next |
| 1.4 | ERP adapters (REST/SOAP/file), reconciliation jobs. | Planned |
| 1.5 | Rule templates, import/export, bulk re-coding. | Planned |
| 1.6 | SSO (OIDC/SAML), SCIM, granular permissions. | Planned |
| 1.7 | Notifications, webhooks, approval workflow for rule changes. | Planned |
| 1.8 | Observability (OpenTelemetry), rate limiting, HA. | Planned |

# PartCode — Implementation Plan

**Version:** 1.1
**Date:** 2026-10-21
**Spec:** `SPEC.md`

---

## 1. Delivery strategy

Build a **vertical slice** first: login → rule → generate → item → audit, backed by a real database and REST API. Then layer the administration UI, PDM contract, and hardening. Every phase ends with a runnable, tested artifact.

The MVP phases remain cross-platform and testable without Windows. Phase 1.2 adds the native PDM add-in in `pdm-connector/`; it compiles against the PDM 2024 interop and is runtime-validated on a Windows vault as a pilot step.

---

## 2. Work breakdown

### Phase 0 — Foundations
| # | Task | Output |
|---|---|---|
| 0.1 | Repository layout and tooling | `backend/`, `frontend/`, `.gitignore`, Makefile |
| 0.2 | Configuration and database bootstrap | settings, engine, session, `create_all` |
| 0.3 | Data model and seed data | tenants, users, rules, counters, items, audit, API keys |
| 0.4 | Security primitives | scrypt hashing, JWT issue/verify, role dependencies |

**Exit:** `GET /api/health` returns 200; demo tenant/user seeded.

### Phase 1 — Rule engine
| # | Task | Output |
|---|---|---|
| 1.1 | Segment schema (discriminated union) | Pydantic models for 7 segment types |
| 1.2 | Validation | per-field errors, final code rules |
| 1.3 | Renderer | deterministic segment rendering |
| 1.4 | Counter reservation | atomic upsert + scope resolution + retry |
| 1.5 | Code generator service | preview (non-consuming) and commit (consuming) |

**Exit:** unit tests cover every segment type, preview, commit, scoped counters, collisions.

### Phase 2 — Core API
| # | Task | Output |
|---|---|---|
| 2.1 | Auth endpoints | login, me |
| 2.2 | Rule endpoints | list/get/create/update(version)/archive |
| 2.3 | Generation endpoints | preview, commit |
| 2.4 | Item endpoints | list/search/get/void/lookup |
| 2.5 | Admin endpoints | users, API keys, audit, stats |
| 2.6 | PDM integration endpoints | reserve/lookup with API key |

**Exit:** OpenAPI covers every endpoint; integration tests pass.

### Phase 3 — Web application
| # | Task | Output |
|---|---|---|
| 3.1 | App shell and auth | login, session persistence, role-aware nav |
| 3.2 | Dashboard | metrics, recent codes, recent audit |
| 3.3 | Generate screen | dynamic rule form, live preview, commit, copy |
| 3.4 | Rules screen | list, create, edit, archive, segment builder |
| 3.5 | Items screen | search, detail, void |
| 3.6 | Audit screen | filters, pagination |
| 3.7 | Settings | users, API keys (secret shown once) |
| 3.8 | Styling | responsive design system, empty/error/loading states |

**Exit:** `npm run build` passes; all flows work against the local API.

### Phase 4 — Hardening and handoff
| # | Task | Output |
|---|---|---|
| 4.1 | Backend tests | auth, RBAC, rules, generation, concurrency, PDM |
| 4.2 | Lint/typecheck | Ruff + `tsc` clean |
| 4.3 | Docs | `README.md`, `.env.example`, run instructions |
| 4.4 | Smoke test | seeded demo script, end-to-end verification |
| 4.5 | Packaging | `Makefile`, Dockerfile (optional) |

**Exit:** fresh clone → install → run in under 5 minutes; tests green.

---

## 3. Milestones

| Milestone | Contents | Definition of done |
|---|---|---|
| M0 | Foundations | Health check, DB seeded |
| M1 | Engine + API | Codes generatable via REST; tests green |
| M2 | Web MVP | A human can log in and generate a code in the browser |
| M3 | Admin + PDM | Rules editable, API keys usable, audit visible |
| M4 | Release candidate | Docs, lint, tests, smoke test |
| M5 | Item linkage | A web-generated code can be linked to an external PDM/ERP reference at generation or afterwards. |

---

## 4. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Rule model too rigid for real customer conventions | Rework | JSON segments + escape hatch (`text` with regex); versioned rules. |
| SQLite write contention | Flaky concurrency tests | Atomic upsert; document PostgreSQL for production. |
| Counter gaps after failed inserts | Cosmetic/audit concern | Document gap policy; never reuse numbers. |
| No real PDM/ERP available | Integration untested | Strict contract, simulator, adapter interface, explicit roadmap. |
| Scope creep (BOM, workflow, SSO) | Missed MVP | Explicit out-of-scope list in `SPEC.md`; roadmap. |
| Secret handling | Security | Hash API keys, scrypt passwords, env-only config, no secrets in git. |
| Code/item terminology causes adoption gaps | Users cannot find how to attach a part | Document that a code is an item; add editable `external_ref`/metadata. |

---

## 5. Verification plan

### Automated
- `pytest` — engine, API, auth, RBAC, concurrency, PDM key flow.
- `ruff check` — backend lint.
- `npm run build` — frontend typecheck + production build.

### Manual smoke test
1. Log in as `admin@demo.local` / seeded password.
2. Create a rule with list + counter segments.
3. Generate a code; verify preview does not increment.
4. Commit; verify the code appears in Items.
5. Generate again; verify the counter advanced.
6. Create an API key; call the PDM endpoint with `X-API-Key`.
7. Edit the rule; verify version 2 and archived version 1.
8. Check the audit log for every action.
9. Generate a code with an external reference, open the registry, and verify the link is visible and editable.

---

## 6. Repository layout

```
SolidWorks_partnumbers/
├── REQUIREMENTS.md
├── SPEC.md
├── PLAN.md
├── README.md
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── .gitignore
├── backend/
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py
│   │   ├── deps.py
│   │   ├── seed.py
│   │   ├── services/
│   │   │   ├── rules.py
│   │   │   ├── generator.py
│   │   │   └── audit.py
│   │   └── api/
│   │       ├── auth.py
│   │       ├── rules.py
│   │       ├── generate.py
│   │       ├── items.py
│   │       ├── admin.py
│   │       └── integrations.py
│   └── tests/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api.ts
        ├── types.ts
        ├── styles.css
        ├── components/
        └── pages/
pdm-connector/
├── PartCode.Connector.Core/
├── PartCode.Connector.Core.Tests/
├── PartCode.Connector.Cli/
├── PartCode.PdmAddIn/
└── installer/
```

---

## 7. Status log

| Date | Phase | Status | Notes |
|---|---|---|---|
| 2026-10-20 | 0–4 | Complete | MVP implemented end-to-end. `pytest` 13 passed, `ruff check` clean, `npm run build` clean, browser smoke test passed with no console errors. |
| 2026-10-21 | 1.1 | Complete | PostgreSQL 17 migration cycle, 12-way counter concurrency, and Docker image build validated. Deployed on Debian 13 with the existing PostgreSQL container and Nginx; runtime and smoke tests passed. |
| 2026-10-20 | 1.2 | Implemented | .NET PDM client, tests, CLI/simulator, net48 COM add-in, PowerShell installer. Add-in builds with zero warnings against PDM 2024 interop; live-vault test pending Windows/PDM. |
| 2026-10-21 | 1.3 | Complete | Added link/metadata fields to web generation, `PATCH /items/{id}`, registry editing, partial unique active-reference index, duplicate 409 handling, audit events, tests, and docs. |

---

## 8. Phase 1.3 — item linkage and metadata (complete)

**Roadmap phase:** 1.3 (replaces the previous ERP-first ordering; ERP moves to 1.4).

**Current behaviour:** A generated part number is already an `items` row. The registry shows each code with `source=web` when it comes from the browser and `source=pdm` when it comes from the connector. The linking field is `external_ref`; it can be set in the web Generate form or edited later in the registry with `PATCH /items/{id}`. PDM is not required to generate or store codes. The PDM add-in still fills the link automatically (`PDM:<vault>:<file-id>`) and writes the code back to the data card.

| # | Task | Output |
|---|---|---|
| 1.3.1 | Clarify code vs item semantics in the UI and docs | Generated code and item are the same record; `external_ref` links it to a PDM/ERP object. |
| 1.3.2 | Link at generation time | Optional external reference, notes, and metadata fields in the web Generate form, passed through `POST /generate`. |
| 1.3.3 | Link after generation | `PATCH /items/{id}` for admin/editor to set or change `external_ref`, notes, and metadata; unique active external reference; audit entry. |
| 1.3.4 | Item detail editing | Show and edit linkage data in the registry detail panel; keep the code string immutable. |
| 1.3.5 | Duplicate and conflict handling | Reject duplicate active `external_ref` with a clear 409 error; allow reuse only after void. |
| 1.3.6 | Verification and documentation | API/UI tests, RBAC tests, audit assertions, and a deployment/end-user explanation of manual linking. |

**Exit criteria met:** A code generated from the web can be linked to a PDM file or ERP object either at generation or afterwards, without deploying the PDM add-in. PDM remains the automatic, write-back path.

**Next:** Phase 1.4 — ERP adapters (REST/SOAP/file) and reconciliation jobs.

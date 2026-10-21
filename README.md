# PartCode

PartCode is a cloud part-numbering service: it owns the coding **rules**, generates unique codes, and exposes them to a web UI, SolidWorks PDM, and ERP through one REST API.

The requirements behind the product are in [`REQUIREMENTS.md`](REQUIREMENTS.md), the product contract is in [`SPEC.md`](SPEC.md), and the delivery plan is in [`PLAN.md`](PLAN.md).

## Documentation

- [End-user guide](docs/wiki/End-User-Guide.md) — how engineers and administrators use the web UI and the PDM add-in.
- [Deployment guide](docs/DEPLOYMENT.md) — Debian 13, Docker, existing PostgreSQL, Nginx, LAN/public TLS, backups, and upgrades.
- [PDM sandbox](sandbox/README.md) — a disposable fake PDM vault and browser UI for testing the connector contract without Windows or PDM.

## What is included

- **Rule engine** — ordered JSON segments (`literal`, `separator`, `list`, `text`, `date`, `counter`, `checksum`), immutable versions, one active version per rule.
- **Code registry** — server-side generation, preview without consuming a number, atomic counters, duplicate protection, voiding, external references, metadata.
- **Web application** — login, dashboard, guided generator, rule editor with live preview, code registry, audit log, users and API keys.
- **REST API** — JWT for people, `X-API-Key` for machines, OpenAPI at `/docs`.
- **PDM contract** — list rules, preview, reserve, lookup, validate; plus configurable ERP lookup and reconciliation adapters.
- **SolidWorks PDM connector** — a .NET Framework 4.8 COM add-in, shared typed client, CLI/simulator, and installer in `pdm-connector/`.
- **PDM sandbox** — a fake vault/data card and browser test UI that sends the same HTTP requests as the add-in, for testing without a Windows PDM environment.
- **Multi-tenant data model** with audit trail on every mutation.
- **Tests** — API, RBAC, rule versioning, generation, scoped counters, concurrency, ERP adapters/reconciliation, and the API-key flow.

The PDM add-in compiles against the PDM 2024 interop but still requires pilot validation on a Windows vault. Generic read-only ERP adapters (stub, file snapshot, REST) are included; vendor-specific SAP/Teamcenter connectors, ERP writes, BOM/workflow, SSO, and billing remain out of scope. See `SPEC.md` §4.5 and `pdm-connector/README.md`.

## Quick start

Requirements: Python 3.12+ and Node.js 20+.

```bash
cp .env.example .env
make install
make dev
```

Open <http://127.0.0.1:8000/app/> and sign in with one of the demo accounts:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@demo.local` | `Admin123!` |
| Editor | `editor@demo.local` | `Editor123!` |
| Viewer | `viewer@demo.local` | `Viewer123!` |

The API is at <http://127.0.0.1:8000/api>, interactive docs at <http://127.0.0.1:8000/docs>.

> The backend serves the compiled frontend from `frontend/dist` at `/app`. Run `make build` and restart the backend after changing the UI. For frontend development, run `make dev-ui` (Vite on port 5173, proxying `/api` to port 8000).

### Manual installation

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cd ../frontend
npm install
npm run build

cd ../backend
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --env-file ../.env
```

### Docker and PostgreSQL

The repository includes a multi-stage `Dockerfile`, `docker-compose.yml`, and Alembic migrations.

```bash
cp .env.example .env
# Set a real JWT_SECRET in .env before exposing the service.
make up
```

For a production rollout with SOLIDWORKS PDM clients, TLS, API-key handling, backups, and upgrades, follow [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

Compose starts PostgreSQL 17 and PartCode, runs `alembic upgrade head`, and serves the prebuilt UI at <http://127.0.0.1:7000/app/>. `AUTO_CREATE_TABLES=false` is set so schema changes go through migrations. Stop with `make down`; data persists in the `partcode-postgres` volume. If you change `POSTGRES_PASSWORD`, keep it URL-safe because it is embedded in `DATABASE_URL`.

## Demo data

On first start with `SEED_DEMO=true`, PartCode creates:

- Tenant `demo` and the three users above.
- Three active rules: `assembly`, `mechanical-part`, and `technical-drawing`.
- A few sample codes so the registry and audit log are not empty.

To start from an empty database, set `SEED_DEMO=false` and remove `backend/partcode.db*`. In development, tables are created automatically from the SQLAlchemy models. In production, set `AUTO_CREATE_TABLES=false` and run `alembic upgrade head`.

## Configuration

Variables are read from the environment (or a `--env-file`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./partcode.db` | SQLAlchemy URL. Use PostgreSQL in production. |
| `JWT_SECRET` | `dev-only-change-me` | HMAC key for access tokens. **Change in production.** |
| `JWT_EXPIRE_MINUTES` | `720` | Access-token lifetime. |
| `CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins for the Vite dev server. |
| `SEED_DEMO` | `true` | Create the demo tenant/users/rules on startup. Set `false` in production. |
| `AUTO_CREATE_TABLES` | `true` | Create tables from models on startup. Set `false` when using Alembic. |
| `ENVIRONMENT` | `development` | Informational environment label. |
| `ERP_ADAPTER` | `stub` | ERP adapter: `stub`, `file`, or `rest`. |
| `ERP_FILE_PATH` | — | JSON/CSV ERP snapshot for the `file` adapter. |
| `ERP_BASE_URL` | — | Base URL for the `rest` adapter. |
| `ERP_LOOKUP_PATH` | `/items/{code}` | REST lookup path; `{code}` is URL-encoded. |
| `ERP_API_KEY` | — | Optional secret sent to the ERP. |
| `ERP_API_KEY_HEADER` | `Authorization` | Header used for `ERP_API_KEY`. |
| `ERP_API_KEY_PREFIX` | `Bearer ` | Prefix added before `ERP_API_KEY`; set empty for raw keys. |
| `ERP_TIMEOUT_SECONDS` | `10` | REST request timeout. |

`.env.example` is a template; `.env` and database files are git-ignored.

## Rule format

A rule is an ordered list of segments plus output constraints:

```json
{
  "segments": [
    { "type": "literal", "value": "PRT" },
    { "type": "separator", "value": "-" },
    {
      "type": "list",
      "key": "family",
      "label": "Family",
      "required": true,
      "options": [
        { "value": "MEC", "label": "Mechanical" },
        { "value": "ELE", "label": "Electrical" }
      ]
    },
    { "type": "separator", "value": "-" },
    {
      "type": "counter",
      "key": "seq",
      "padding": 5,
      "start": 1,
      "step": 1,
      "scope": "per_value",
      "scope_keys": ["family"]
    }
  ],
  "max_length": 64,
  "case": "upper"
}
```

Supported segment types:

| Type | Behaviour |
|---|---|
| `literal` | Fixed text. |
| `separator` | Fixed punctuation. |
| `list` | Value must be one of the configured options. |
| `text` | Free text with optional `min`, `max`, and `regex`. |
| `date` | `strftime` pattern evaluated in UTC at generation time. |
| `counter` | Zero-padded progressive number with `start`, `step`, and `rule` or `per_value` scope. |
| `checksum` | `mod97` or `luhn`, computed over the rendered prefix. |

Every edit creates a new immutable version. Activating a new version archives the previously active one; previews and generated items record the exact rule version used. Draft versions can coexist with the active version without changing generation behaviour.

Counters are reserved with a single atomic upsert (`ON CONFLICT … DO UPDATE … RETURNING`) and the unique `(tenant_id, code)` constraint is the final collision guard. Failed generations may leave gaps; numbers are never reused.

## API overview

All endpoints are under `/api`. Human endpoints use `Authorization: Bearer <token>`; integration endpoints use `X-API-Key: pk_live_…`. Timestamps are ISO 8601 UTC.

| Method | Path | Role | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | public | Obtain a JWT. |
| `GET` | `/auth/me` | any user | Current user. |
| `GET/POST` | `/rules` | read: any; write: editor | List latest rules / create a rule. |
| `GET` | `/rules/{id}` | any user | Rule detail. |
| `GET` | `/rules/{id}/versions` | any user | Version history. |
| `PUT` | `/rules/{id}` | editor | Save a new version. |
| `POST` | `/rules/{id}/archive` | editor | Archive a version. |
| `POST` | `/generate/preview` | any user | Render without consuming a counter. |
| `POST` | `/generate` | any user | Commit a code. |
| `GET` | `/items` | any user | Search the registry. |
| `GET` | `/items/{id}` | any user | Code detail. |
| `GET` | `/items/lookup?code=…` | any user | Lookup by code. |
| `PATCH` | `/items/{id}` | editor | Edit external reference, notes, or metadata. |
| `POST` | `/items/{id}/void` | editor | Void a code. |
| `GET` | `/admin/users` | admin | Users. |
| `POST` | `/admin/users` | admin | Create a user. |
| `PATCH` | `/admin/users/{id}` | admin | Role or active state. |
| `GET/POST` | `/admin/api-keys` | admin | List / create keys (secret shown once). |
| `DELETE` | `/admin/api-keys/{id}` | admin | Revoke a key. |
| `GET` | `/admin/audit` | admin, editor | Filtered audit log. |
| `GET` | `/admin/stats` | any user | Dashboard metrics. |
| `GET` | `/integrations/pdm/rules` | API key | Active rules for a document type. |
| `POST` | `/integrations/pdm/preview` | API key | Preview for a connector. |
| `POST` | `/integrations/pdm/reserve` | API key | Reserve a code with `source=pdm`. |
| `GET` | `/integrations/pdm/lookup?code=…` | API key | Code lookup. |
| `GET` | `/integrations/pdm/validate?code=…` | API key | Alias of lookup. |
| `GET` | `/integrations/erp/lookup?code=…` | API key | Look up a code in the configured ERP adapter. |
| `POST` | `/integrations/erp/reconcile` | API key | Compare items with ERP and commit matched reservations. |

### Example: generate a code

```bash
TOKEN=$(curl -s http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.local","password":"Admin123!"}' | jq -r .access_token)

curl -s http://127.0.0.1:8000/api/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"rule_key":"mechanical-part","values":{"family":"MEC"},"metadata":{"material":"AISI 304"}}'
```

### Example: PDM reserve

Create a key in **Users & API keys**, then:

```bash
curl -s http://127.0.0.1:8000/api/integrations/pdm/reserve \
  -H "X-API-Key: pk_live_…" \
  -H 'Content-Type: application/json' \
  -d '{
    "rule_key": "mechanical-part",
    "values": {"family": "MEC"},
    "external_ref": "PDM:12345",
    "metadata": {"description": "Bracket"}
  }'
```

The response includes `code`, `rule_version`, `item_id`, and the rendered `segments`. A connector should store `item_id`/`code` in the PDM data card and use `external_ref` for idempotent ERP reconciliation.

Each generated code is itself an item in the registry; there is no separate part record to create. `source` records where it came from (`web` or `pdm`), and `external_ref` is the link to a PDM/ERP object. Web users can set the link while generating or edit it later:

```bash
curl -s -X PATCH http://127.0.0.1:8000/api/items/<item_id> \
  -H "Authorization: Bearer <token>" \
  -H 'Content-Type: application/json' \
  -d '{
    "external_ref": "PDM:SandboxVault:1001",
    "notes": "Linked from the registry",
    "metadata": {"material": "S355", "description": "Bracket"}
  }'
```

PDM remains the automatic write-back path, but linking no longer requires the add-in. An external reference is unique across active items; void the old item before reusing its reference.

## ERP adapters

Set `ERP_ADAPTER` to choose a read-only lookup source:

- `stub` (default) — always reports "not found"; useful when ERP integration is not configured.
- `file` — reads a JSON or CSV snapshot from `ERP_FILE_PATH`. JSON can be a list of objects, an object with an `items` list, or a mapping of code to object. CSV needs a `code` column; `id`/`external_id`, `status`, and `description` are optional.
- `rest` — calls `ERP_BASE_URL + ERP_LOOKUP_PATH` with `GET`. A `404` means not found; a JSON object may contain `code`, `id`/`external_id`, `status`, `description`, or `{"found": false}`. Other HTTP or transport failures return `502`.

The lookup is exposed to API-key clients:

```bash
curl -s "http://127.0.0.1:8000/api/integrations/erp/lookup?code=PRT-MEC-00001" \
  -H "X-API-Key: pk_live_…"
```

Reconciliation checks non-void PartCode items against ERP. A `reserved` item found in ERP becomes `committed`; missing items are reported but not downgraded. Use `dry_run` to preview, and `codes` to limit the run (maximum 200 items per run):

```bash
curl -s -X POST http://127.0.0.1:8000/api/integrations/erp/reconcile \
  -H "X-API-Key: pk_live_…" \
  -H 'Content-Type: application/json' \
  -d '{"dry_run": true, "limit": 100}'
```

Each status change writes an `item.committed` audit event. ERP is authoritative: PartCode never overwrites ERP data, and `propose_item` is not exposed as a write endpoint in this version.

## Development

```bash
make test             # backend pytest suite
make lint             # Ruff check + frontend typecheck/build
make build            # production frontend build
make format           # Ruff formatter (backend)
make migrate          # apply Alembic migrations to the configured DB
make migration m="…"  # autogenerate a new migration
make connector-test   # .NET client tests
make connector-build  # build the add-in, client, and CLI
make sandbox-up       # start the fake PDM vault sandbox on :7100
make sandbox-down     # stop the sandbox
make up / make down   # Docker Compose with PostgreSQL
```

Backend layout:

```
backend/app/
├── main.py            FastAPI app, lifespan, static mount
├── config.py          environment settings
├── db.py              engine, sessions, SQLite pragmas
├── models.py          tenants, users, rules, counters, items, audit, keys
├── schemas.py         Pydantic request/response models
├── security.py        scrypt hashing, JWT, API-key hashing
├── deps.py            auth dependencies and role checks
├── seed.py            demo tenant and rules
├── services/          rule versioning, generator, audit, errors
├── services/erp/      stub/file/REST adapters and reconciliation
└── api/               auth, rules, generation, items, admin, integrations
```

Frontend layout:

```
frontend/src/
├── App.tsx            session and page routing
├── api.ts             typed API client
├── styles.css         design system and responsive layout
├── components/        shell, icons, UI primitives
└── pages/             login, dashboard, generate, rules, editor,
                       registry, audit, settings
```

Connector layout:

```
pdm-connector/
├── PartCode.Connector.Core/       typed PDM API client (netstandard2.0 / net8.0)
├── PartCode.Connector.Core.Tests/ xUnit tests with a fake HTTP handler
├── PartCode.Connector.Cli/        cross-platform CLI and PDM simulator
├── PartCode.PdmAddIn/             PDM Professional COM add-in (net48, WinForms)
└── installer/                     PowerShell install/uninstall + DPAPI config
```

Sandbox layout:

```
sandbox/
├── docker-compose.yml
├── .env.example
└── pdm-mock/          fake PDM API + browser test UI
```

See `pdm-connector/README.md` for build, install, settings, and current limitations.
See `sandbox/README.md` for the no-Windows connector test.

## Production notes

- Use PostgreSQL (`DATABASE_URL=postgresql+psycopg://…`) and a strong `JWT_SECRET`.
- Set `SEED_DEMO=false`; create the first administrator through your provisioning process.
- Serve behind HTTPS. The SPA and API can share an origin, so CORS can stay narrow.
- SQLite is for development and single-process demos. Counter atomicity is correct, but write concurrency is limited.
- Schema changes are managed by Alembic. Keep `AUTO_CREATE_TABLES=false` in production and run `alembic upgrade head` before starting the app.
- Docker Compose runs the migration automatically. The `Dockerfile` serves the built SPA from the same origin as the API.
- API keys are stored as SHA-256 hashes and shown once. Rotate keys by creating a new one and revoking the old one.
- ERP integration is read-only lookup/reconciliation. Validate the adapter against the customer's ERP contract before using `rest`; the `file` adapter needs a readable snapshot mounted into the container.

## License

Internal prototype. Add a license before distributing.

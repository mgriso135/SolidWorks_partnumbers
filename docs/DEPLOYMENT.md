# PartCode deployment guide

This guide deploys PartCode on a Debian 13 (trixie) server using Docker, an
existing PostgreSQL container, and Nginx. It assumes a single-server
installation for a pilot or small production deployment.

PartCode does not need to be exposed to the internet. It can run entirely on a
private LAN using an internal DNS name or a private IP address. Public DNS and
Let's Encrypt are one option; an internal CA, a self-signed certificate, or an
isolated HTTP-only test network are also valid.

It covers:

- Preparing the server.
- Reusing the PostgreSQL container that is already running on the host.
- Building and starting the PartCode container.
- Creating the tenant and the first administrator.
- Publishing the application through Nginx and Let's Encrypt.
- Smoke tests, backups, upgrades, rollback, and troubleshooting.

The repository also contains a `docker-compose.yml` that starts its **own**
PostgreSQL container. That is useful for a disposable test, but this guide
reuses the existing database server. Appendix A describes the bundled Compose
option.

---

## 1. Architecture

```text
LAN / internet clients
          |
          | HTTP :7000 (or HTTPS on the configured TLS port)
          v
   +-------------------+
   | Nginx on Debian   |
   | TLS or LAN HTTP   |
   +---------+---------+
              | HTTP 127.0.0.1:7001
              v
   +-------------------+        private Docker network
   | PartCode container|  ------------------------------+
   | FastAPI + SPA     |                                |
   | Alembic migrations|                                v
   +-------------------+                     +---------------------+
                                             | Existing PostgreSQL |
                                             | container           |
                                             | database: partcode  |
                                             +---------------------+
```

The PartCode image contains the compiled React application and the FastAPI
backend. It runs database migrations on startup and then starts Uvicorn. Only
Nginx should be reachable from client machines; the application port is bound
to `127.0.0.1`.

---

## 2. Before you start

### 2.1 Assumptions

- Debian 13 with `sudo`, SSH, and Docker already installed.
- An existing PostgreSQL container, version 14 or newer. PostgreSQL 17 is the
  version exercised by the project's migration tests. This guide creates a
  dedicated `partcode` role and database inside it. Do not reuse an existing
  application database.
- A stable name or address for the server. This can be a public DNS name such as
  `partcode.example.com`, an internal DNS name such as `partcode.lan`, or a
  private IP address such as `192.168.1.249`.
- TLS is strongly recommended on any network where real credentials are used.
  Public DNS can use Let's Encrypt; a LAN can use an internal CA or a
  self-signed certificate. Section 9.2 covers all three options.
- The ports you choose are free and reachable from the intended clients. This
  guide uses Nginx on `7000` and publishes the application on loopback `7001`,
  because another service already uses `8000` on this server. If you use public
  TLS, ports 80 and 443 must be reachable from the internet; a LAN-only
  deployment can restrict `7000` to the LAN subnet.
- You can copy this repository to the server, for example with `rsync` or a Git
  clone.

### 2.2 Deployment worksheet

Replace these placeholders consistently. Keep the values in a password manager
or secret store.

| Variable | Example | Notes |
|---|---|---|
| `DOMAIN` | `192.168.1.249` | Public/internal DNS name or private IP used by users and integrations. |
| `PG_CONTAINER` | `global_production_postgres` | Name from `docker ps`. |
| `PG_NETWORK` | `shared-prod-net` | Existing user-defined Docker network the PostgreSQL container is on. |
| `WEB_PORT` | `7000` | Port users open in the browser; Nginx listens here. |
| `APP_PORT` | `7001` | Loopback-only host port for PartCode; Nginx proxies to it. |
| `DB_PASSWORD` | generated | Use a URL-safe password. `openssl rand -hex 24` is ideal. |
| `JWT_SECRET` | generated | At least 32 random bytes. `openssl rand -hex 48`. |
| `ADMIN_EMAIL` | `admin@example.com` | First PartCode administrator. |
| `ADMIN_PASSWORD` | generated | At least 12 characters. |
| `TENANT_NAME` | `Kaizen Key` | Company name shown in the tenant record. |
| `LETSENCRYPT_EMAIL` | `it@example.com` | Only needed for public Let's Encrypt certificates. |

Run the commands in this guide in a single shell session. Set the non-secret
values first:

```bash
export DOMAIN="192.168.1.249"
export PG_CONTAINER="global_production_postgres"
export PG_NETWORK="shared-prod-net"
export WEB_PORT="7000"
export APP_PORT="7001"
export ADMIN_EMAIL="mgriso@kaizenkey.com"
export TENANT_NAME="Kaizen Key"
export LETSENCRYPT_EMAIL="it@example.com"  # only for public Let's Encrypt
export BASE_URL="http://${DOMAIN}:${WEB_PORT}"  # change scheme after enabling TLS
```

Generate the two secrets **once** and save them in your password manager:

```bash
export DB_PASSWORD="$(openssl rand -hex 24)"
export JWT_SECRET="$(openssl rand -hex 48)"
```

Do not re-run the two `openssl` commands after the deployment: they would
replace the database password and the JWT signing key. If you reconnect in a new
shell, retrieve the existing values from your secret store; the JWT secret and
database password are also present in `/home/matteo/apps-production/partcode/.env.production` once that
file is created. Do not echo either secret into logs or terminal transcripts.

### 2.3 Public internet or local network

Both are supported; nothing in PartCode requires public exposure.

**Local network (common for a pilot):**

- Give the server a stable private address, for example `192.168.1.249`.
- Put that address in `DOMAIN`, or create an internal DNS record such as
  `partcode.lan`. For a handful of clients, add a hosts-file entry instead:
  `192.168.1.249 partcode.lan`.
- Nginx listens on `7000`; publish the application only on
  `127.0.0.1:7001`. Only Nginx should listen on the LAN. Restrict the firewall
  to the LAN subnet (section 3).
- Choose one TLS option:
  - Internal CA (recommended for a company LAN): use your AD Certificate
    Services, `step-ca`, or `mkcert`, and distribute the root CA to clients.
  - Self-signed certificate: acceptable for a small test group, but every
    browser and PDM client must import and trust it.
  - HTTP only: acceptable only on an isolated or trusted test network. Passwords
    and bearer tokens travel in clear text; do not use this on a shared LAN.
- The SOLIDWORKS PDM clients must trust the certificate as well. Import the
  internal root CA into the Windows machine trust store on each PDM client.

**Internet-facing:**

- Use a public DNS name with an A/AAAA record, open ports 80 and 443, and obtain
  a Let's Encrypt certificate with the HTTP-01 flow in section 9.2.
- If the public DNS name points at a private address, HTTP-01 will not work;
  use DNS-01 with a certbot DNS plugin, or stay with an internal CA.

### 2.4 Important limitations of this release

Read these before exposing the service:

- There is no self-service password reset and no password-change screen. The
  bootstrap procedure in section 8 can also reset the first admin password.
- There is no MFA, SSO, rate limiting, or login lockout. Put the service behind
  TLS and, if it is internet-facing, consider a VPN or Nginx IP allowlist.
- The web UI's login page contains demo-account shortcuts. With
  `SEED_DEMO=false` they do not work, but they are still displayed. Remove or
  adapt `frontend/src/pages/Login.tsx` before a broad end-user rollout if that
  is confusing or undesirable.
- The API documentation at `/docs` and the OpenAPI schema are public by
  default. Restrict them at the proxy if your policy requires it.
- The JWT is stored in browser `localStorage`. Use HTTPS, restrict who can
  modify served frontend assets, and treat any XSS as a credential-theft risk.
- ERP lookup/reconciliation is read-only (stub, file, or REST). There is no ERP
  write-back in this version. The SOLIDWORKS PDM add-in is compile-verified but
  still requires a pilot on a real Windows vault.
- This is a single-tenant pilot deployment. The data model supports tenants,
  but no tenant-management UI is included.
- Counters are never reused. Failed generations may leave gaps.

---

## 3. Prepare the Debian server

Update the system and install the proxy and diagnostic tools:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y nginx certbot python3-certbot-nginx ufw curl jq ca-certificates
```

If the upgrade installed a new kernel, reboot before continuing:

```bash
test -f /var/run/reboot-required && sudo reboot || true
```

Reconnect and re-export the shell variables if you rebooted. Make sure Docker
and time synchronization are active:

```bash
sudo systemctl enable --now docker
sudo systemctl enable --now nginx
sudo systemctl status docker --no-pager
timedatectl set-ntp true
timedatectl status
```

Configure the firewall. Keep SSH open before enabling UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 7000/tcp
sudo ufw --force enable
sudo ufw status verbose
```

On a LAN-only server, replace the broad `Nginx Full` rule with subnet-scoped
rules. Adjust `192.168.1.0/24` to your LAN:

```bash
sudo ufw delete allow 7000/tcp
sudo ufw allow from 192.168.1.0/24 to any port 7000 proto tcp
sudo ufw allow from 192.168.1.0/24 to any port 7443 proto tcp
sudo ufw status verbose
```

If you choose public Let's Encrypt later, also allow 80 and 443 from the
internet.

Do not publish PostgreSQL port 5432 on the public interface. The existing
container should stay on a private Docker network. If it currently publishes
`0.0.0.0:5432`, remove that mapping or restrict it to `127.0.0.1:5432` in the
PostgreSQL Compose file.

---

## 4. Prepare the existing PostgreSQL container

### 4.1 Identify the container and its network

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' | grep -i postgres
```

Set `PG_CONTAINER` to the name in the first column. Inspect its networks:

```bash
sudo docker inspect \
  -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' \
  "$PG_CONTAINER"
```

The output lists one network name per line. Reuse the user-defined network that
PostgreSQL is already on. On this server that is `shared-prod-net`, so set:

```bash
export PG_NETWORK="shared-prod-net"
```

Confirm that PostgreSQL is attached:

```bash
sudo docker network inspect "$PG_NETWORK" \
  --format '{{range .Containers}}{{.Name}} {{end}}'
```

The output must list the PostgreSQL container. No `docker network create` or
`docker network connect` is needed when you reuse an existing network: the
PartCode container simply joins it with `--network "$PG_NETWORK"`.

Reusing a shared network lets PartCode reach every container on that network.
If that is not acceptable, create a separate network and connect PostgreSQL to
both; keep `shared-prod-net` attached if other services still need it. Only if
PostgreSQL is on the default `bridge` network do you need to create a network
first:

```bash
sudo docker network create partcode-net 2>/dev/null || true
sudo docker network connect partcode-net "$PG_CONTAINER" 2>/dev/null || true
export PG_NETWORK="partcode-net"
```

Do not use the default `bridge` network for application-to-database traffic:
container-name DNS does not work there reliably.

> If PostgreSQL is recreated by another Compose project, Compose normally
> reattaches `shared-prod-net` automatically because it is declared in that
> project. If you attached the network manually instead, re-run the
> `docker network connect` command after re-creation.

### 4.2 Create the role and database

Find the PostgreSQL superuser configured in the container:

```bash
sudo docker exec "$PG_CONTAINER" env | grep '^POSTGRES_'
```

In the official image this is usually `postgres`. Set it if necessary:

```bash
  export PG_SUPERUSER="postgres"
```

The SQL below interpolates `DB_PASSWORD` inside single quotes. The recommended
`openssl rand -hex 24` value contains only hexadecimal characters and is safe. If
you use a different password, avoid single quotes or escape them for SQL.

Create the role, or update its password if it already exists:

```bash
ROLE_EXISTS=$(sudo docker exec "$PG_CONTAINER" \
  psql -U "$PG_SUPERUSER" -d postgres -tAc \
  "SELECT 1 FROM pg_roles WHERE rolname='partcode'")

if [ "$ROLE_EXISTS" = "1" ]; then
  sudo docker exec -i "$PG_CONTAINER" \
    psql -U "$PG_SUPERUSER" -d postgres -c \
    "ALTER ROLE partcode WITH LOGIN PASSWORD '$DB_PASSWORD';"
else
  sudo docker exec -i "$PG_CONTAINER" \
    psql -U "$PG_SUPERUSER" -d postgres -c \
    "CREATE ROLE partcode LOGIN PASSWORD '$DB_PASSWORD';"
fi
```

Create the database only if it does not exist:

```bash
DB_EXISTS=$(sudo docker exec "$PG_CONTAINER" \
  psql -U "$PG_SUPERUSER" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='partcode'")

if [ "$DB_EXISTS" != "1" ]; then
  sudo docker exec -i "$PG_CONTAINER" \
    psql -U "$PG_SUPERUSER" -d postgres -c \
    "CREATE DATABASE partcode OWNER partcode;"
fi
```

If the database already existed but was owned by another role, make the
dedicated role its owner (only safe because this database is dedicated to
PartCode):

```bash
sudo docker exec -i "$PG_CONTAINER" \
  psql -U "$PG_SUPERUSER" -d postgres -c \
  "ALTER DATABASE partcode OWNER TO partcode;"
```

### 4.3 Test connectivity and authentication

Run a temporary client container on the same network. This verifies both DNS
and the credentials before PartCode is started:

```bash
sudo docker run --rm --network "$PG_NETWORK" \
  -e PGPASSWORD="$DB_PASSWORD" postgres:16-alpine \
  psql -h "$PG_CONTAINER" -U partcode -d partcode \
  -c 'SELECT current_user, current_database();'
```

Expected output is `partcode | partcode`. If this fails, fix the network,
password, or `pg_hba.conf` before continuing.

Record the database password in a password manager. It is also written to the
application environment file in the next section.

---

## 5. Copy the application to the server

Create the deployment directory:

```bash
sudo install -d -o "$USER" -g "$USER" /home/matteo/apps-production/partcode
```

From your workstation, copy the repository. Adjust the SSH user and server.
The exclusions avoid uploading local secrets, SQLite files, and build output:

```bash
rsync -av \
  --exclude='.env' \
  --exclude='backend/partcode.db*' \
  --exclude='backend/.venv' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='bin/' \
  --exclude='obj/' \
  ./ deploy@SERVER:/home/matteo/apps-production/partcode/
```

Alternatively, clone the repository directly on the server into
`/home/matteo/apps-production/partcode`. The server does not need Python, Node.js, or npm; the Docker
build performs both installs inside the image.

The application directory should look like this:

```text
/home/matteo/apps-production/partcode/
├── Dockerfile
├── backend/
├── frontend/
├── docs/
└── ...
```

---

## 6. Create the production environment file

The image reads configuration from environment variables. Create a protected
environment file:

```bash
(umask 077
cat > /home/matteo/apps-production/partcode/.env.production <<EOF
DATABASE_URL=postgresql+psycopg://partcode:${DB_PASSWORD}@${PG_CONTAINER}:5432/partcode
JWT_SECRET=${JWT_SECRET}
JWT_EXPIRE_MINUTES=720
CORS_ORIGINS=${BASE_URL}
SEED_DEMO=false
AUTO_CREATE_TABLES=false
ENVIRONMENT=production
# ERP is read-only. Keep stub until the ERP contract is validated.
ERP_ADAPTER=stub
# ERP_FILE_PATH=/data/erp-items.json
# ERP_BASE_URL=https://erp.example/api
# ERP_LOOKUP_PATH=/items/{code}
# ERP_API_KEY=change-me
# ERP_API_KEY_HEADER=Authorization
# ERP_TIMEOUT_SECONDS=10
EOF
)
chmod 600 /home/matteo/apps-production/partcode/.env.production
```

Notes:

- `CORS_ORIGINS` is taken from `BASE_URL`; make sure `BASE_URL` is exported
  before running the heredoc, and that it matches the scheme and host users
  actually type. Update it and recreate the container if you add TLS later.
- `DATABASE_URL` points at the PostgreSQL **container name**, not `localhost`.
- Use a URL-safe database password. If it contains reserved URL characters such
  as `@`, `:`, `/`, `?`, `#`, or `%`, percent-encode them or regenerate it with
  `openssl rand -hex 24`.
- `SEED_DEMO=false` prevents the demo tenant, users, sample rules, and sample
  codes from being created.
- `AUTO_CREATE_TABLES=false` makes Alembic migrations the only schema authority.
  The container runs `alembic upgrade head` before Uvicorn starts.
- Changing `JWT_SECRET` invalidates all existing sessions; users must sign in
  again.
- `CORS_ORIGINS` is mainly relevant if the frontend and API are served from
  different origins. Keeping the exact origin users type here is harmless.
- The file contains secrets. Never commit it, copy it into an image, or attach it
  to a support ticket.
- Environment variables are read when the container is created. After editing
  this file, recreate the container with the `docker rm`/`docker run` commands
  in section 7; `docker restart` alone does not reload the environment.

### 6.1 Optional ERP adapter

The default `ERP_ADAPTER=stub` reports every code as not found. To validate ERP
connectivity without changing PartCode code:

- `ERP_ADAPTER=file` reads a JSON/CSV snapshot from `ERP_FILE_PATH`. The file
  must exist **inside the container**; add a read-only volume such as
  `-v /srv/partcode/erp-items.json:/data/erp-items.json:ro` and set
  `ERP_FILE_PATH=/data/erp-items.json`.
- `ERP_ADAPTER=rest` sends `GET {ERP_BASE_URL}{ERP_LOOKUP_PATH}` with an optional
  API key. A `404` means "not found"; other HTTP/transport errors are reported
  as `502`. The container needs outbound network access to the ERP.
- `ERP_LOOKUP_PATH` must contain `{code}`. The default is `/items/{code}`.
- `item.committed` audit events are written only when a `reserved` item is found
  in ERP and the reconciliation is not a dry run.

Validate lookup and a dry run before enabling a live reconciliation:

```bash
curl -s "https://partcode.example/api/integrations/erp/lookup?code=PRT-MEC-00001" \
  -H "X-API-Key: $PARTCODE_API_KEY"

curl -s -X POST https://partcode.example/api/integrations/erp/reconcile \
  -H "X-API-Key: $PARTCODE_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"dry_run": true, "limit": 100}'
```

Recreate the container after changing ERP variables. The endpoints use the
`X-API-Key` header, not a browser JWT.

---

## 7. Build and start PartCode

Build the image on the server:

```bash
cd /home/matteo/apps-production/partcode
sudo docker build --no-cache -t partcode:1.0.0 .
```

The build runs `npm ci`, produces the frontend bundle, installs the Python
dependencies, and creates the runtime image. The first build typically takes a
few minutes.

Start the container. It is attached to the same network as PostgreSQL. Uvicorn
still listens on `8000` inside the container; only host loopback port `7001` is
published. Nginx will listen on `7000` and proxy to `7001`:

```bash
sudo docker rm -f partcode 2>/dev/null || true
sudo docker run -d \
  --name partcode \
  --restart unless-stopped \
  --network "$PG_NETWORK" \
  --env-file /home/matteo/apps-production/partcode/.env.production \
  -p 127.0.0.1:7001:8000 \
  partcode:1.0.0
```

Watch the startup sequence. You should see Alembic run the migrations and then
Uvicorn start listening on `0.0.0.0:8000` inside the container:

```bash
sudo docker ps --filter name=partcode
sudo docker logs --tail 100 partcode
```

Verify the application locally:

```bash
curl -fsS http://127.0.0.1:7001/api/health
```

Expected response:

```json
{"status":"ok","service":"partcode","version":"1.0.0"}
```

If the container exits, read the logs and see the troubleshooting section. At
this point the API is healthy but the database has no users: the next step
creates the tenant and first administrator.

### 7.1 Startup behavior

- The container command is
  `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- If PostgreSQL is not ready yet, the container exits and Docker retries it
  according to the restart policy. After a host reboot the database may need a
  few seconds to accept connections.
- `docker stop` sends a normal termination signal. PartCode keeps no local
  state, so stopping and recreating the container does not lose data. All data
  lives in PostgreSQL.
- Keep a single application container for this pilot. The schema migrations are
  designed to run once at startup.

---

## 8. Bootstrap the tenant and first administrator

With `SEED_DEMO=false` the database is intentionally empty and there is no
public signup endpoint. Use the following idempotent script inside the running
container. It creates a tenant if none exists, creates the admin user, or resets
the same user's password and role if it already exists.

```bash
read -rsp 'New admin password: ' ADMIN_PASSWORD; echo
sudo docker exec -i \
  -e TENANT_NAME="$TENANT_NAME" \
  -e ADMIN_EMAIL="$ADMIN_EMAIL" \
  -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  partcode python - <<'PY'
import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Tenant, User
from app.security import hash_password

tenant_name = os.environ.get("TENANT_NAME", "PartCode").strip() or "PartCode"
email = os.environ["ADMIN_EMAIL"].strip().lower()
password = os.environ["ADMIN_PASSWORD"]

if len(password) < 12:
    raise SystemExit("ADMIN_PASSWORD must be at least 12 characters")

with SessionLocal() as db:
    tenant = db.scalar(select(Tenant).order_by(Tenant.created_at))
    if tenant is None:
        tenant = Tenant(name=tenant_name, slug="default")
        db.add(tenant)
        db.flush()

    user = db.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == email)
    )
    if user is None:
        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
        db.add(user)
        action = "created"
    else:
        user.password_hash = hash_password(password)
        user.role = "admin"
        user.active = True
        action = "updated"

    db.commit()
    print(f"Admin {email} {action} in tenant {tenant.slug} ({tenant.id})")
PY
unset ADMIN_PASSWORD
```

The command above passes the password as an environment variable to a short
lived process. On a shared or audited server, avoid placing real passwords
directly in command history; run the command with a leading space if
`HISTCONTROL=ignorespace` is configured, or clear the relevant history entry
afterwards.

Test the login immediately:

```bash
read -rsp 'Admin password: ' ADMIN_PASSWORD; echo
TOKEN=$(curl -fsS "http://127.0.0.1:7001/api/auth/login" \
  -H 'Content-Type: application/json' \
  --data "$(jq -nc --arg email "$ADMIN_EMAIL" --arg password "$ADMIN_PASSWORD" \
    '{email: $email, password: $password}')" \
  | jq -r .access_token)
unset ADMIN_PASSWORD

test -n "$TOKEN" && echo "Login OK"
curl -fsS "http://127.0.0.1:7001/api/admin/stats" \
  -H "Authorization: Bearer $TOKEN" | jq '{active_rules, items_total, items_today}'
```

The initial stats should show zero rules and zero items. Sign in through the web
UI later to create the real rules and additional users.

---

## 9. Publish with Nginx (TLS optional on a LAN)

### 9.1 Nginx reverse proxy

Create `/etc/nginx/sites-available/partcode`. Nginx listens on `${WEB_PORT}`
(`7000`) and proxies to the loopback app port `${APP_PORT}` (`7001`):

```bash
sudo tee /etc/nginx/sites-available/partcode >/dev/null <<EOF
server {
    listen ${WEB_PORT};
    listen [::]:${WEB_PORT};
    server_name ${DOMAIN};

    client_max_body_size 2m;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    location = / {
        return 302 /app/;
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
EOF
```

Enable the site and validate the configuration:

```bash
sudo ln -sfn /etc/nginx/sites-available/partcode /etc/nginx/sites-enabled/partcode
sudo nginx -t
sudo systemctl reload nginx
```

Before adding TLS, check that the name resolves and HTTP reaches PartCode. On a
LAN, `getent hosts` may return an internal DNS or hosts-file entry; using the IP
directly is also valid:

```bash
getent hosts "$DOMAIN"
curl -fsS "http://${DOMAIN}:${WEB_PORT}/api/health"
```

### 9.2 TLS certificates

Choose the option that matches how clients reach the server.

#### Option A: Public DNS with Let's Encrypt

This option uses the standard ports 80/443 instead of the LAN port 7000. In the
Nginx site from section 9.1, change `listen ${WEB_PORT}` to `listen 80` and
`listen [::]:${WEB_PORT}` to `listen [::]:80` first. After TLS works, set
`BASE_URL="https://${DOMAIN}"`.

Once public DNS points to this server and port 80 is reachable from the
internet:

```bash
sudo certbot --nginx \
  -d "$DOMAIN" \
  --redirect \
  --agree-tos \
  --no-eff-email \
  -m "$LETSENCRYPT_EMAIL"
```

Certbot edits the Nginx site to listen on 443 and redirect HTTP to HTTPS. Check
automatic renewal:

```bash
systemctl list-timers | grep -i certbot || true
sudo certbot renew --dry-run
```

After TLS works, verify:

```bash
curl -fsS "${BASE_URL}/api/health"
curl -fsSI "http://${DOMAIN}/app/" | head
```

With public TLS, the second command should redirect to HTTPS. In HTTP-only
mode it should return the application page directly.

#### Option B: Local network with an internal CA

Use your company PKI, `step-ca`, or `mkcert`. The certificate must include the
name or IP that clients type in its Subject Alternative Name (SAN); modern
clients ignore the old Common Name field.

Place the certificate and key on the server, for example:

```bash
sudo install -d -m 700 /etc/ssl/partcode
sudo install -m 644 fullchain.pem /etc/ssl/partcode/fullchain.pem
sudo install -m 600 privkey.pem  /etc/ssl/partcode/privkey.pem
```

In `/etc/nginx/sites-available/partcode`, add a redirect server and enable TLS
in the existing server block:

```nginx
server {
    listen 7000;
    listen [::]:7000;
    server_name 192.168.1.249;
    return 301 https://$host:7443$request_uri;
}

server {
    listen 7443 ssl;
    listen [::]:7443 ssl;
    server_name 192.168.1.249;

    ssl_certificate     /etc/ssl/partcode/fullchain.pem;
    ssl_certificate_key /etc/ssl/partcode/privkey.pem;

    # Keep the add_header and location blocks from section 9.1 here.
}
```

After enabling TLS, set `BASE_URL="https://${DOMAIN}:7443"`, update
`CORS_ORIGINS` in `.env.production` to the same origin, and recreate the
application container.

Validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Distribute the issuing root CA to every client:

- Debian/Ubuntu:
  `sudo cp partcode-root.crt /usr/local/share/ca-certificates/` then
  `sudo update-ca-certificates`.
- Windows PDM clients: import the root CA into *Local Computer > Trusted Root
  Certification Authorities*, preferably through Group Policy. Install it in
  the machine store, not only the current user's store.
- Firefox keeps its own trust store; import the root CA there separately if it
  is used.
- For command-line tests before the CA is installed system-wide, use
  `curl --cacert /path/to/partcode-root.crt "${BASE_URL}/api/health"`.

A self-signed certificate works for a small test group, but every browser and
PDM client must import and trust it. Prefer an internal CA or `mkcert`.

#### Option C: HTTP only on an isolated test network

For a short-lived pilot on a trusted, segmented LAN, you can skip TLS:

1. Keep the Nginx site on `${WEB_PORT}` and do not run `certbot`.
2. Set `CORS_ORIGINS=http://${DOMAIN}:${WEB_PORT}` in `.env.production` and
   recreate the application container.
3. Set `BASE_URL="http://${DOMAIN}:${WEB_PORT}"` in your shell and use that URL
   in the smoke tests.
4. Restrict port `7000` (and `7443` if you use internal TLS) to the LAN subnet
   in the firewall.
5. Open `http://${DOMAIN}:${WEB_PORT}/app/` in a browser on the LAN.

Anyone on that network can read passwords and bearer tokens in transit. Do not
use HTTP-only mode on guest Wi-Fi, a flat corporate network, or anything
reachable from the internet.

### 9.3 Quick test with an SSH tunnel

If Nginx or DNS is not ready, you can test the application without exposing it
on the LAN. Use an SSH tunnel from your workstation:

```bash
ssh -L 7000:127.0.0.1:7001 deploy@SERVER
```

Then open `http://127.0.0.1:7000/app/` in your local browser. This is suitable
only for testing, not for real credentials or production use.

### 9.4 Optional: restrict the API documentation

If the public API docs are not appropriate for your environment, add a location
block before the catch-all `location /`:

```nginx
location = /docs {
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny all;
    proxy_pass http://127.0.0.1:7001;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Also restrict `/openapi.json` and `/redoc` if you use this approach, otherwise
the schema or an alternate documentation page is still available. Reload Nginx
after any change with `sudo nginx -t && sudo systemctl reload nginx`.

---

## 10. Smoke tests

### 10.1 Web application

1. Open `${BASE_URL}/app/` in a browser. For a private CA, make sure the CA is
   trusted by that browser first.
2. Sign in with the admin email and password from section 8.
3. Open **Coding rules**, create a rule (for example `smoke-part` with a
   literal `TST`, a separator `-`, and a counter with padding 3), and publish it
   as active.
4. Open **Generate code**, select the rule, preview the code, then generate it.
5. Confirm the new code appears in **Code registry**.
6. Open **Audit log** and confirm the sign-in and generation events.
7. Create a viewer or editor user in **Users & API keys**, then test that user
   in a private browser window.

### 10.2 API and database

With the admin token from section 8 still exported:

```bash
curl -fsS "${BASE_URL}/api/admin/stats" \
  -H "Authorization: Bearer $TOKEN" | jq

sudo docker exec "$PG_CONTAINER" \
  psql -U partcode -d partcode \
  -c 'SELECT status, COUNT(*) FROM items GROUP BY status;'
```

### 10.3 Machine-to-machine path (optional)

This verifies the same path the PDM connector uses. It creates a temporary
rule, API key, reservation, and lookup; cleanup commands follow.

```bash
RULE=$(curl -fsS "${BASE_URL}/api/rules" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{
    "name": "Deployment smoke test",
    "description": "Temporary deployment verification rule",
    "document_type": "part",
    "key": "deployment-smoke",
    "status": "active",
    "definition": {
      "segments": [
        {"type": "literal", "value": "TST"},
        {"type": "separator", "value": "-"},
        {"type": "counter", "key": "seq", "padding": 3, "start": 1,
         "step": 1, "scope": "rule", "scope_keys": []}
      ],
      "max_length": 16,
      "case": "upper"
    }
  }')
RULE_ID=$(printf '%s' "$RULE" | jq -r .id)

KEY_RESPONSE=$(curl -fsS "${BASE_URL}/api/admin/api-keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"name": "deployment smoke test"}')
KEY=$(printf '%s' "$KEY_RESPONSE" | jq -r .key)
KEY_ID=$(printf '%s' "$KEY_RESPONSE" | jq -r .id)

curl -fsS "${BASE_URL}/api/integrations/pdm/rules?document_type=part" \
  -H "X-API-Key: $KEY" | jq

RESERVED=$(curl -fsS "${BASE_URL}/api/integrations/pdm/reserve" \
  -H "X-API-Key: $KEY" \
  -H 'Content-Type: application/json' \
  --data '{"rule_key": "deployment-smoke", "values": {},
           "external_ref": "deployment-smoke-1"}')
printf '%s' "$RESERVED" | jq
CODE=$(printf '%s' "$RESERVED" | jq -r .code)

curl -fsS "${BASE_URL}/api/integrations/pdm/lookup?code=${CODE}" \
  -H "X-API-Key: $KEY" | jq '.exists, .item.code'
```

Expected lookup output includes `true` and `TST-001` on a fresh database.

Clean up the temporary key and rule:

```bash
curl -fsS -X DELETE "${BASE_URL}/api/admin/api-keys/${KEY_ID}" \
  -H "Authorization: Bearer $TOKEN" | jq
curl -fsS -X POST "${BASE_URL}/api/rules/${RULE_ID}/archive" \
  -H "Authorization: Bearer $TOKEN" | jq '{key, version, status}'
```

Archiving does not delete the smoke-test rule, because rules are never deleted.
On a real production database, use the UI to create a real rule instead of this
temporary one. The generated smoke-test code can be voided in the registry if
desired.

---

## 11. SOLIDWORKS PDM client rollout

The PDM add-in is a separate Windows component. Server deployment only makes
the API available to it.

1. In PartCode, sign in as admin and create an API key named for the vault.
   Copy it once into the installer's protected input.
2. On a Windows PDM client, build or obtain the Release output of
   `pdm-connector/PartCode.PdmAddIn`.
3. Run the elevated PowerShell installer with the base URL and API key. Use the
   same scheme and host as `BASE_URL`; on a LAN this may be a private IP:

   ```powershell
   .\pdm-connector\installer\Install-PartCodePdmAddIn.ps1 `
     -BaseUrl "http://192.168.1.249:7000" `
     -ApiKeyFile "C:\Temp\partcode-pdm-key.txt" `
     -DocumentType "part" `
     -TargetVariable "PartNumber"
   ```

   If you use HTTPS with an internal CA, import the root CA into the Windows
   machine trust store before running the add-in.

4. Add the installed DLL in **PDM Administration > Add-ins** and enable it for
   the vault.
5. Restart the PDM client.
6. Test on a non-production vault first: select a file, run
   **PartCode: assign code...**, preview, reserve, and confirm that the target
   data-card variable is written.

The add-in stores the API key with machine-scope DPAPI in
`%ProgramData%\PartCode\pdm-connector.json`. It uses a 30-second HTTP timeout and
sends metadata only. See `pdm-connector/README.md` for configuration,
troubleshooting, and known limitations.

Use a dedicated API key per vault or integration so it can be revoked without
breaking other clients.

---

## 12. Backups

All application data is in PostgreSQL. Back up the database and the environment
file; the container image is reproducible from the repository.

### 12.1 Manual backup

```bash
sudo install -d -m 750 /var/backups/partcode
set -o pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

sudo docker exec \
  -e PGPASSWORD="$DB_PASSWORD" \
  "$PG_CONTAINER" \
  pg_dump -U partcode -d partcode -Fc \
  | gzip \
  | sudo tee "/var/backups/partcode/partcode-${STAMP}.dump.gz" >/dev/null

set +o pipefail
sudo chmod 600 "/var/backups/partcode/partcode-${STAMP}.dump.gz"
sudo ls -lh /var/backups/partcode/
```

Verify that the dump is readable:

```bash
sudo bash -c 'gzip -t /var/backups/partcode/partcode-*.dump.gz'
```

### 12.2 Scheduled backup

Create `/etc/partcode-backup.env`, readable only by root. The single quotes keep
shell-special characters in the password from being expanded; a hexadecimal
password needs no special handling.

```bash
sudo install -m 600 /dev/null /etc/partcode-backup.env
sudo tee /etc/partcode-backup.env >/dev/null <<EOF
PG_CONTAINER=${PG_CONTAINER}
PARTCODE_DB_PASSWORD='${DB_PASSWORD}'
EOF
```

Create `/usr/local/sbin/partcode-backup`:

```bash
sudo tee /usr/local/sbin/partcode-backup >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -a
source /etc/partcode-backup.env
set +a

install -d -m 750 /var/backups/partcode
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

docker exec \
  -e PGPASSWORD="$PARTCODE_DB_PASSWORD" \
  "$PG_CONTAINER" \
  pg_dump -U partcode -d partcode -Fc \
  | gzip > "/var/backups/partcode/partcode-${STAMP}.dump.gz"

chmod 600 "/var/backups/partcode/partcode-${STAMP}.dump.gz"
find /var/backups/partcode -type f -name 'partcode-*.dump.gz' -mtime +14 -delete
EOF
sudo chmod 700 /usr/local/sbin/partcode-backup
```

Test it once:

```bash
sudo /usr/local/sbin/partcode-backup
sudo ls -lh /var/backups/partcode/
```

Schedule it daily at 02:30 with root's crontab:

```bash
echo '30 2 * * * /usr/local/sbin/partcode-backup >> /var/log/partcode-backup.log 2>&1' \
  | sudo tee /etc/cron.d/partcode-backup >/dev/null
sudo chmod 644 /etc/cron.d/partcode-backup
```

Also back up `/home/matteo/apps-production/partcode/.env.production` and `/etc/partcode-backup.env` in a
secure secret store. They are required to restore the service and decrypt
access to the database. Backups contain personal data and API-key hashes; store
and transfer them encrypted. Copy backups off the server regularly.

### 12.3 Test a restore

Stop the application, restore into the same database, and start it again:

```bash
sudo docker stop partcode
set -o pipefail

sudo gunzip -c /var/backups/partcode/partcode-YYYYMMDDTHHMMSSZ.dump.gz \
  | sudo docker exec -i \
      -e PGPASSWORD="$DB_PASSWORD" \
      "$PG_CONTAINER" \
      pg_restore -U partcode -d partcode --clean --if-exists --no-owner

set +o pipefail
sudo docker start partcode
```

Alternatively restore into a scratch database without touching production:

```bash
sudo docker exec -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
  createdb -h 127.0.0.1 -U partcode partcode_restore

sudo gunzip -c /var/backups/partcode/partcode-YYYYMMDDTHHMMSSZ.dump.gz \
  | sudo docker exec -i \
      -e PGPASSWORD="$DB_PASSWORD" \
      "$PG_CONTAINER" \
      pg_restore -U partcode -d partcode_restore --no-owner

sudo docker exec -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
  psql -h 127.0.0.1 -U partcode -d partcode_restore \
  -c 'SELECT COUNT(*) FROM items;'

sudo docker exec -e PGPASSWORD="$DB_PASSWORD" "$PG_CONTAINER" \
  dropdb -h 127.0.0.1 -U partcode partcode_restore
```

Test restores on a schedule; an unverified backup is not a backup.

---

## 13. Upgrades and rollback

Treat every upgrade as a maintenance window. The container runs migrations on
startup, so a failed migration can stop the service.

### 13.1 Upgrade procedure

1. Announce a short maintenance window.
2. Take a database backup and copy it off the server.
3. Copy the new source into `/home/matteo/apps-production/partcode`.
4. Build a new image with a new tag:

   ```bash
   cd /home/matteo/apps-production/partcode
   sudo docker build --no-cache -t partcode:1.1.0 .
   ```

5. Stop and remove the old container. Its data is in PostgreSQL, not in the
   container:

   ```bash
   sudo docker stop partcode
   sudo docker rm partcode
   ```

6. Start the new image with the same environment file and network:

   ```bash
   sudo docker run -d \
     --name partcode \
     --restart unless-stopped \
     --network "$PG_NETWORK" \
     --env-file /home/matteo/apps-production/partcode/.env.production \
     -p 127.0.0.1:7001:8000 \
     partcode:1.1.0
   ```

7. Watch the migration and startup:

   ```bash
   sudo docker logs -f --tail 200 partcode
   ```

8. Run the health check and a login smoke test:

   ```bash
   curl -fsS http://127.0.0.1:7001/api/health
   curl -fsS "${BASE_URL}/api/health"
   ```

9. Keep the previous image tag until the new version has been stable for a
   reasonable period. Docker does not delete it automatically if it is tagged.

### 13.2 Rollback

If the new application version fails before changing the schema, start the
previous image:

```bash
sudo docker stop partcode
sudo docker rm partcode
sudo docker run -d \
  --name partcode \
  --restart unless-stopped \
  --network "$PG_NETWORK" \
  --env-file /home/matteo/apps-production/partcode/.env.production \
  -p 127.0.0.1:7001:8000 \
  partcode:1.0.0
```

If a migration changed the schema and the old image is not compatible, restore
the database backup taken before the upgrade, then start the previous image.
Alembic downgrades exist only where a migration explicitly provides them; do
not assume an automatic downgrade is safe.

---

## 14. Routine operations

### 14.1 Logs and status

```bash
sudo docker ps --filter name=partcode
sudo docker logs --tail 200 -f partcode
sudo docker inspect --format '{{json .State.Health}}' partcode | jq
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

The image has a built-in health check that calls `/api/health` every 30 seconds
from inside the container. Docker marks the container healthy or unhealthy, but
does not restart it on health failure. Use an external monitor if you need
automated alerting.

### 14.2 Restart and stop

```bash
sudo docker restart partcode
sudo docker stop partcode
sudo docker start partcode
```

### 14.3 Check the database

```bash
sudo docker exec -it "$PG_CONTAINER" \
  psql -U partcode -d partcode
```

Useful queries:

```sql
SELECT COUNT(*) FROM items;
SELECT status, COUNT(*) FROM items GROUP BY status;
SELECT action, COUNT(*) FROM audit_log GROUP BY action ORDER BY 2 DESC;
SELECT key, version, status FROM rules ORDER BY key, version DESC;
```

### 14.4 Disk and retention

Monitor the Docker volumes, PostgreSQL data directory, backups, and logs. The
audit log and item registry grow forever in this version. Plan retention or
archival at the database level if required by your company policy; do not delete
audit rows casually, because they are the traceability record.

---

## 15. Security hardening checklist

- Use HTTPS everywhere real credentials or API keys are used. HTTP is acceptable
  only on an isolated, trusted test LAN.
- Keep port 7001 bound to `127.0.0.1`; only Nginx should expose port 7000.
- Keep PostgreSQL on a private Docker network and do not publish 5432.
- Use long random `JWT_SECRET` and database passwords; store them in a secret
  manager and the protected environment file.
- Set `SEED_DEMO=false` and `AUTO_CREATE_TABLES=false`.
- Create named admin/editor/viewer accounts instead of sharing the first admin.
- Create one API key per PDM vault or integration, and revoke retired keys.
- Review the audit log periodically for unexpected rule changes or logins.
- Restrict `/docs` and `/openapi.json` at Nginx if they should not be public.
- Consider a VPN or IP allowlist for the whole service if it is internet-facing.
- Apply Debian, Docker, Nginx, and PartCode updates on a schedule.
- Test backups and restores, and keep an off-server copy.
- Remember there is no MFA, SSO, login throttling, or self-service password reset
  in this release.

---

## 16. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Container exits immediately, logs mention `connection refused` or `could not translate host name` | PostgreSQL is not on the same Docker network, `PG_CONTAINER` is wrong, or the database is not ready. Run the connectivity test from section 4.3. |
| Logs mention `password authentication failed for user "partcode"` | `DB_PASSWORD` in `.env.production` does not match the role password. Reset the role password and update the file. |
| Logs mention `permission denied for schema public` | The database owner/privileges are wrong. Make `partcode` the database owner or grant the required schema privileges. |
| `alembic upgrade head` fails | Read the exact SQL error. Check database ownership and disk space, and restore the pre-upgrade backup if necessary. |
| Nginx fails with `address already in use` for port 7000 | Another site or service owns 7000. Check `sudo ss -ltnp '( sport = :7000 )'`, then either stop the other service or choose another `WEB_PORT`. |
| `docker run` reports `bind: address already in use` for port 7001 | Another service uses loopback port 7001. Choose another host port (for example `-p 127.0.0.1:7002:8000`) and update `proxy_pass` in Nginx. |
| `curl http://127.0.0.1:7001/api/health` fails but the container is running | Port mapping or startup is incomplete. Check `docker logs partcode` and `docker port partcode`. |
| Nginx returns 502 Bad Gateway | The app is not listening on `127.0.0.1:7001`, or the container is stopped. Check `docker ps`, logs, and `curl` locally. |
| Nginx returns 404 for `/app/` | The image is missing the frontend build, or a custom image was built incorrectly. Rebuild with the repository `Dockerfile` and inspect `/app/frontend/dist` in the image. |
| Data disappears after the container is recreated | `DATABASE_URL` is probably still pointing at SQLite. It must start with `postgresql+psycopg://` and point at the PostgreSQL container. |
| Login fails with the credentials just created | The bootstrap script may have targeted a different tenant or database, or the password contains characters altered by the shell. Re-run the bootstrap script idempotently. |
| Demo login shortcuts fail | Expected when `SEED_DEMO=false`. Use the real admin account. |
| A connector receives `401 Unauthorized` | The API key is missing, mistyped, revoked, or belongs to another tenant. Create a new key in the UI and update the connector. |
| PDM add-in reports a config error | Run the installer or set `PARTCODE_PDM_CONFIG`; verify `%ProgramData%\PartCode\pdm-connector.json` exists. |
| PDM write fails after the code is reserved | The code still exists in PartCode. Fix the PDM variable/permission issue and reconcile manually; do not invent a replacement code. |
| A generated code is too long | The rule's `max_length` is exceeded. Shorten the text input or have an editor adjust the rule in a new version. |
| The preview shows one code but generation returns another | Another user reserved the counter between preview and generation. This is normal; use the final generated code. |
| A number is missing from the sequence | A failed generation may have consumed it. Gaps are intentional; numbers are never reused. |
| Login redirects back or session ends quickly | JWT expired (`JWT_EXPIRE_MINUTES`) or `JWT_SECRET` changed. Sign in again. |
| Let's Encrypt certificate issuance fails | For a private IP or an internal-only name such as `partcode.lan`, HTTP-01 cannot work. Use an internal CA or self-signed certificate instead. For public DNS, check `getent hosts`, port 80, UFW, and `nginx -t`. |
| Browser shows a certificate error on a LAN | The internal root CA or self-signed certificate is not trusted on that client. Import the root CA into the browser/OS trust store, and into the Windows machine store for PDM clients. |
| Browser shows a certificate error after renewal | Nginx was not reloaded, or the certificate is for another name/IP. Run `sudo nginx -t && sudo systemctl reload nginx` and inspect the certificate SANs. |

For deeper investigation:

```bash
sudo docker logs --tail 300 partcode
sudo journalctl -u nginx --no-pager -n 100
sudo docker network inspect "$PG_NETWORK"
sudo docker exec -it partcode sh
```

Inside the container, the application lives in `/app/backend` and the compiled
frontend in `/app/frontend/dist`.

---

## 17. Deployment checklist

Use this as a final sign-off list:

- [ ] Debian server updated; Docker, Nginx, and UFW enabled.
- [ ] PostgreSQL container identified and on the existing user-defined `$PG_NETWORK` network.
- [ ] Dedicated `partcode` role and database created.
- [ ] Connectivity test from a container succeeds.
- [ ] Repository copied to `/home/matteo/apps-production/partcode` without local `.env` or SQLite files.
- [ ] `.env.production` created with mode `600`, strong secrets, `SEED_DEMO=false`,
      and `AUTO_CREATE_TABLES=false`.
- [ ] Image built and container running with `--restart unless-stopped`.
- [ ] `/api/health` returns `ok` locally and through Nginx.
- [ ] First tenant and admin created; login tested.
- [ ] Nginx site enabled; TLS configured (Let's Encrypt, internal CA, or
      self-signed) and trust/renewal verified. HTTP-only only for an isolated
      test LAN.
- [ ] Web UI smoke test: create rule, preview, generate, registry, audit.
- [ ] API-key/PDM path tested and temporary credentials cleaned up.
- [ ] Backup script tested and scheduled; restore procedure documented.
- [ ] Previous image tag retained for rollback.
- [ ] Admin accounts, API-key ownership, and `/docs` exposure reviewed.
- [ ] PDM add-in piloted on a non-production vault (if used).

---

## Appendix A. Bundled Docker Compose test stack

For a disposable test, the repository's `docker-compose.yml` starts PartCode
and its own PostgreSQL 17 container. This does **not** use the existing
PostgreSQL container and should not be used for the same production data.

```bash
cd /home/matteo/apps-production/partcode
cp .env.example .env
```

Edit `.env`:

```dotenv
POSTGRES_PASSWORD=<url-safe-password>
JWT_SECRET=<long-random-secret>
SEED_DEMO=false
CORS_ORIGINS=http://192.168.1.249:7000
```

Use the scheme, host, and port you will actually open in `CORS_ORIGINS`. This
example publishes the app directly on port 7000. Do not run it while the Nginx
deployment from section 9 is using that port.

To restrict direct access to loopback, change the published port in
`docker-compose.yml` from `"7000:8000"` to `"127.0.0.1:7000:8000"` and use an
SSH tunnel. Then start it:

```bash
sudo docker compose up -d --build
sudo docker compose logs -f app
curl -fsS http://127.0.0.1:7000/api/health
```

The first-admin bootstrap command from section 8 works the same way. Replace
`sudo docker exec -i partcode python -` with
`sudo docker compose exec -T app python -`, keeping the same `-e` variables.
Data is stored in the `partcode-postgres` Docker volume; use
`docker compose down` to stop the services without deleting the volume.

Because Compose manages its own database and network, do not mix it with the
existing-PostgreSQL deployment on the same host unless you intentionally want
two independent installations.

---

## Appendix B. Quick command reference

After the initial deployment, these are the commands you are most likely to
need. Re-export `DOMAIN`, `BASE_URL`, `WEB_PORT`, `APP_PORT`, `PG_CONTAINER`,
`PG_NETWORK`, and `DB_PASSWORD` first if you are in a new shell.

```bash
# Status and logs
sudo docker ps --filter name=partcode
sudo docker logs --tail 200 -f partcode

# Health
curl -fsS http://127.0.0.1:7001/api/health
curl -fsS "${BASE_URL}/api/health"

# Restart
sudo docker restart partcode

# Database shell
sudo docker exec -it "$PG_CONTAINER" psql -U partcode -d partcode

# Manual backup
sudo /usr/local/sbin/partcode-backup

# Nginx validation and reload
sudo nginx -t && sudo systemctl reload nginx

# Certificate renewal check (public Let's Encrypt only)
sudo certbot renew --dry-run
```

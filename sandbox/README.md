# PartCode PDM sandbox

A disposable fake PDM vault for testing the PartCode connector without Windows,
SOLIDWORKS, or a real PDM vault.

It is **not** a SolidWorks PDM API server. PDM exposes a local COM/.NET API
(`IEdmVault5`, `IEdmFile5`, `IEdmEnumeratorVariable5`), so it cannot be recreated
faithfully on Linux. The sandbox emulates the boundary that matters:

```text
fake PDM file + data card
          |
          |  same HTTP calls as the real add-in
          v
PartCode /api/integrations/pdm/rules | preview | reserve | lookup
          |
          v
code written back to the fake data card
```

PartCode remains the only authority for rules and counter allocation. The
sandbox only plays the role of the PDM client.

## What it gives you

- A fake vault with three files and editable-in-code data-card variables.
- A browser UI to select a rule, preview, reserve, and see the code written to
  the fake `PartNumber` variable.
- The same `source=pdm`, `external_ref=PDM:<vault>:<file-id>`, metadata, and
  duplicate-external-reference behavior as the real add-in.
- A reset button, so each test starts clean.
- No database or external Python dependencies; state is in memory.

## Quick start

Requirements: Docker with Compose, plus a running PartCode server and an API
key.

1. In PartCode, sign in as an administrator and open **Users & API keys**.
   Create a key, for example `PDM sandbox`, and copy the secret.
2. Make sure at least one active rule exists for the document type you will test
   (default `part`). The demo rules include `mechanical-part`.
3. Configure and start the sandbox:

```bash
cd sandbox
cp .env.example .env
# edit .env and set PARTCODE_API_KEY
docker compose up -d --build
```

4. Open <http://127.0.0.1:7100> on the server, or use the tunnel/LAN options below.

If the sandbox runs on the same machine as PartCode, keep the default
`PARTCODE_URL=http://host.docker.internal:7000`. Do not use the server's LAN IP
from inside the container: UFW may allow port `7000` only from the LAN subnet
and drop traffic from the Docker bridge.

If PartCode is on another machine, set its LAN URL, for example:

```dotenv
PARTCODE_URL=http://192.168.1.249:7000
```

For a remote server, the default `SANDBOX_BIND=127.0.0.1` keeps the sandbox on
the server's loopback interface. Use an SSH tunnel from your workstation:

```bash
ssh -L 7100:127.0.0.1:7100 user@192.168.1.249
```

Then open <http://127.0.0.1:7100> locally.

To open the sandbox directly on the LAN, set this in `.env` and recreate the
container:

```dotenv
SANDBOX_BIND=0.0.0.0
```

```bash
docker compose up -d
```

Then allow TCP `7100` from the LAN only:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 7100 proto tcp
```

The sandbox has no authentication and holds a PartCode API key. Do not expose
it to an untrusted network or the internet. If the browser hangs when opening
the LAN address, check the binding and firewall:

```bash
sudo ss -ltnp | grep ':7100'
sudo ufw status
```

The listener must be `0.0.0.0:7100` (or the LAN address), not
`127.0.0.1:7100`.

### `Could not load rules from PartCode ... timed out`

This means the sandbox container cannot reach the PartCode host port. On a
same-host deployment, test the host gateway from inside the container:

```bash
sudo docker exec <sandbox-container> python -c \
  "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:7000/api/health', timeout=5).read().decode())"
```

If that times out, UFW is probably dropping traffic from the Docker bridge.
Use one of these fixes:

1. **Allow the Docker bridge to reach PartCode.** Find the sandbox subnet:

   ```bash
   sudo docker network inspect partcode-solidworks-pdm-fake_default \
     -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
   sudo ufw allow from <sandbox-subnet> to any port 7000 proto tcp
   ```

   Keep `PARTCODE_URL=http://host.docker.internal:7000` and recreate the
   container.

2. **Use host networking for the sandbox.** This works only when the sandbox
   and PartCode are on the same host. In `docker-compose.yml`, remove the
   `ports` and `extra_hosts` entries, add `network_mode: host`, and set:

   ```dotenv
   PARTCODE_URL=http://127.0.0.1:7000
   ```

   Then recreate the container. The sandbox listens on host port `7100`
   directly.

3. **Join PartCode's Docker network.** If the PartCode container is named
   `partcode` on `shared-prod-net`, attach the sandbox to that network and set:

   ```dotenv
   PARTCODE_URL=http://partcode:8000
   ```

   This bypasses Nginx and the host firewall entirely.

## Test flow

1. Open the sandbox UI.
2. Pick a fake file and an active rule.
3. Select **Preview**. This calls `/api/integrations/pdm/preview`; no number is
   consumed and no data card is changed.
4. Select **Reserve and write**. The sandbox calls
   `/api/integrations/pdm/reserve`; PartCode allocates the code; the sandbox
   writes it to the fake `PartNumber` field.
5. Open PartCode **Code registry** and search for the code. It should show
   `source=pdm` and `external_ref=PDM:SandboxVault:<file-id>`.
6. Select **Reserve and write** again for the same file. PartCode returns
   `DUPLICATE_EXTERNAL_REF` and the sandbox shows the existing code. This is the
   same protection the real add-in relies on.
7. Select **Reset fake file** to test again, or reset everything:

```bash
curl -X POST http://127.0.0.1:7100/api/reset
```

## API examples

```bash
curl -s http://127.0.0.1:7100/health
curl -s http://127.0.0.1:7100/api/files
curl -s http://127.0.0.1:7100/api/rules

curl -s -X POST http://127.0.0.1:7100/api/files/1001/preview \
  -H 'Content-Type: application/json' \
  -d '{"rule_key":"mechanical-part","values":{"family":"MEC"}}'

curl -s -X POST http://127.0.0.1:7100/api/files/1001/reserve \
  -H 'Content-Type: application/json' \
  -d '{"rule_key":"mechanical-part","values":{"family":"MEC"}}'
```

## Run without Docker

```bash
cd sandbox/pdm-mock
PARTCODE_URL=http://192.168.1.249:7000 \
PARTCODE_API_KEY=pk_live_... \
python3 app.py
```

Then open <http://127.0.0.1:7100>.

Configuration:

| Variable | Default | Purpose |
|---|---|---|
| `PARTCODE_URL` | `http://host.docker.internal:7000` | PartCode base URL, including the Nginx port. |
| `PARTCODE_API_KEY` | empty | API key created in PartCode. Required for rules and assignment. |
| `PDM_VAULT` | `SandboxVault` | Fake vault name used in the external reference. |
| `DOCUMENT_TYPE` | `part` | Rule document type loaded by the sandbox. |
| `TARGET_VARIABLE` | `PartNumber` | Fake data-card variable that receives the code. |
| `PARTCODE_TLS_INSECURE` | `false` | Test-only: skip certificate verification for self-signed HTTPS. |
| `PORT` | `7100` | Sandbox listening port when run directly. |
| `SANDBOX_BIND` | `127.0.0.1` | Host address Docker publishes. Use `0.0.0.0` only for isolated LAN testing. |

The fake data card uses the same default source mapping as the real connector:

```text
Description -> description
Material    -> material
Family      -> family
```

The UI pre-fills list/text rule fields whose key or label matches a data-card
variable. The demo files use `Family=MEC` and `Family=ELE`, which work with the
seed `mechanical-part` rule.

## Replacing it with real PDM

PartCode does not need to change. The real add-in uses the same endpoints and
payload shape as this sandbox. To switch:

1. Keep the PartCode server and API key.
2. Install the add-in on a Windows machine with the SOLIDWORKS PDM Professional
   client.
3. Configure `baseUrl`, `documentType`, `targetVariable`, and
   `sourceVariables` the same way.
4. Replace the fake file and fake data card with a real vault file.
5. Enable the add-in for the vault in PDM Administration.

The sandbox cannot test the COM add-in DLL itself, file check-in/out, PDM
permissions, workflows, or configuration-specific data-card tabs. Those require
a Windows pilot against a real test vault.

## Limitations

- In-memory state; restarting the container resets all fake files.
- No authentication or TLS. Bind it to loopback and use it for testing only.
- No real PDM versioning, check-in/out, workflow, permissions, BOM, or COM API.
- Only the connector contract is emulated, not PDM's full API.

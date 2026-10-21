# PartCode PDM connector

This solution contains the SolidWorks PDM integration for PartCode.

| Project | Target | Purpose |
|---|---|---|
| `PartCode.Connector.Core` | netstandard2.0 / net8.0 | Typed HTTP client for the PDM API and shared models. |
| `PartCode.Connector.Core.Tests` | net10.0 | Client tests with a fake HTTP handler. |
| `PartCode.Connector.Cli` | net8.0 | Cross-platform CLI and PDM simulator for connector testing. |
| `PartCode.PdmAddIn` | net48 | SOLIDWORKS PDM Professional add-in (COM, WinForms). |
| `installer` | PowerShell | Per-machine add-in installation, COM registration, DPAPI key storage. |

## What the add-in does

1. The user selects a file in a PDM vault and chooses **PartCode: assign code...**.
2. The add-in reads the file's data-card variables (`Description`, `Material`, `Family` by default).
3. It loads the active PartCode rules for the configured document type.
4. The user picks a rule, fills any list/text fields, and previews the code.
5. On reserve, PartCode atomically allocates a unique code.
6. The add-in writes the code to the configured PDM variable (`PartNumber` by default) and flushes the data card.

The connector never computes codes locally. PartCode remains the only authority for rule evaluation and counter allocation.

For the full server + PDM client rollout, see [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).

## Build and test

Requires the .NET SDK. The add-in also needs .NET Framework 4.8 on the PDM client machine; building the `net48` project on Linux is supported with `EnableWindowsTargeting`.

```bash
dotnet test pdm-connector/PartCode.Connector.slnx
dotnet build pdm-connector/PartCode.PdmAddIn/PartCode.PdmAddIn.csproj -c Release
```

The PDM interop assemblies are supplied by the `BlueByte.SOLIDWORKS.PDMProfessional.Interops` NuGet package (PDM 2024 interop). No PDM installation is required to compile, but runtime validation requires a Windows machine with SOLIDWORKS PDM Professional.

## Install on Windows

1. Build the add-in in `Release`.
2. In an elevated PowerShell, from the repository root:

```powershell
.\pdm-connector\installer\Install-PartCodePdmAddIn.ps1 `
  -BaseUrl "https://partcode.example.com" `
  -ApiKeyFile "C:\Temp\partcode-pdm-key.txt" `
  -DocumentType "part" `
  -TargetVariable "PartNumber"
```

Omit `-ApiKeyFile` to be prompted for the key instead. Avoid putting the key
directly in shell history on shared machines.

The script:

- Copies the add-in and dependencies to `%ProgramFiles%\PartCode\PdmAddIn`.
- Registers the COM class with 64-bit `RegAsm`.
- Protects the API key with machine-scope DPAPI and writes `%ProgramData%\PartCode\pdm-connector.json`.
- Restricts the config directory ACL.

Then add the DLL in **PDM Administration > Add-ins** and enable it for the vault. Restart the PDM client.

## Configure

`%ProgramData%\PartCode\pdm-connector.json`:

```json
{
  "baseUrl": "https://partcode.example.com",
  "apiKeyProtected": "<base64 DPAPI blob>",
  "documentType": "part",
  "targetVariable": "PartNumber",
  "sourceVariables": {
    "Description": "description",
    "Material": "material",
    "Family": "family"
  }
}
```

`sourceVariables` maps a PDM data-card variable name to a PartCode field/metadata name. The add-in also passes PDM path, file ID, file name, and vault name as metadata, and uses `PDM:<vault>:<file-id>` as the external reference for idempotent ERP reconciliation.

For development, a plaintext `apiKey` field is also accepted. The config lookup order is:

1. `%PARTCODE_PDM_CONFIG%`
2. `%ProgramData%\PartCode\pdm-connector.json`
3. `%LOCALAPPDATA%\PartCode\pdm-connector.json`

## CLI / simulator

The CLI exercises the same API contract the add-in uses and is useful for connector acceptance tests without Windows:

```bash
export PARTCODE_URL=http://127.0.0.1:8000
export PARTCODE_API_KEY=pk_live_...

dotnet run --project pdm-connector/PartCode.Connector.Cli -- rules --document-type part
dotnet run --project pdm-connector/PartCode.Connector.Cli -- \
  preview --rule mechanical-part --value family=MEC
dotnet run --project pdm-connector/PartCode.Connector.Cli -- \
  reserve --rule mechanical-part --value family=MEC \
  --external-ref PDM:DemoVault:12345 --metadata description="Bracket"
dotnet run --project pdm-connector/PartCode.Connector.Cli -- lookup --code PRT-MEC-00006
```

Create an API key in PartCode under **Users & API keys**. Machine clients use it as `X-API-Key`; no user JWT is involved.

## Current limitations

- The add-in is **compile-verified on Linux against the PDM 2024 interop**, but has not been run against a live PDM vault in this environment. Perform a pilot on a Windows test vault before production.
- The installer is a PowerShell script, not an MSI. MSI/WiX packaging remains a later step.
- The add-in is manually invoked from the file context menu. It does not yet auto-reserve on check-in, and it does not create PDM workflows or BOMs.
- Writing a code assumes the target variable already exists on the file data card.
- If the PDM write fails after PartCode reserve, the code remains reserved. The UI reports the error; the file is not silently updated. A reconciliation/void action is a future enhancement.
- A 30-second HTTP timeout is used; large files are never uploaded, only metadata is sent.

## Troubleshooting

- Add-in not visible: verify the DLL is enabled in PDM Administration, the client was restarted, and `RegAsm` registration succeeded.
- `401 Unauthorized`: the API key is wrong, revoked, or belongs to another tenant.
- `Config not found`: run the installer or set `PARTCODE_PDM_CONFIG`.
- Errors are appended to `%LOCALAPPDATA%\PartCode\pdm-addin.log` (no API key is logged).

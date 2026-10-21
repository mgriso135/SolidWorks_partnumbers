#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$destination = Join-Path $env:ProgramFiles "PartCode\PdmAddIn"
$dll = Join-Path $destination "PartCode.PdmAddIn.dll"
$regAsm = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"

if (Test-Path $dll) {
    & $regAsm $dll /unregister
}

if (Test-Path $destination) {
    Remove-Item $destination -Recurse -Force
}

Write-Host "PartCode PDM add-in unregistered and removed."
Write-Host "Remove it from PDM Administration > Add-ins if it is still listed."
Write-Host "Configuration remains in $env:ProgramData\PartCode\pdm-connector.json."

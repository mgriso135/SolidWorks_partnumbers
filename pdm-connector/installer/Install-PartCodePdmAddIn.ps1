#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [string]$ApiKey,
    [string]$ApiKeyFile,

    [string]$DocumentType = "part",
    [string]$TargetVariable = "PartNumber",
    [string]$BuildConfiguration = "Release"
)

$ErrorActionPreference = "Stop"

if (-not [string]::IsNullOrWhiteSpace($ApiKeyFile)) {
    if (-not (Test-Path -LiteralPath $ApiKeyFile)) {
        throw "API key file not found: $ApiKeyFile"
    }
    $ApiKey = (Get-Content -Raw -LiteralPath $ApiKeyFile).Trim()
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $secure = Read-Host "PartCode API key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "An API key is required. Pass -ApiKey, -ApiKeyFile, or enter it when prompted."
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$source = Join-Path $repositoryRoot "pdm-connector\PartCode.PdmAddIn\bin\$BuildConfiguration\net48"
$addInDll = Join-Path $source "PartCode.PdmAddIn.dll"

if (-not (Test-Path $addInDll)) {
    throw "Add-in build not found at $addInDll. Run: dotnet build pdm-connector/PartCode.PdmAddIn/PartCode.PdmAddIn.csproj -c $BuildConfiguration"
}

$destination = Join-Path $env:ProgramFiles "PartCode\PdmAddIn"
New-Item -ItemType Directory -Force -Path $destination | Out-Null

Copy-Item (Join-Path $source "*.dll") $destination -Force
$configSource = Join-Path $source "PartCode.PdmAddIn.dll.config"
if (Test-Path $configSource) {
    Copy-Item $configSource $destination -Force
}

$regAsm = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"
if (-not (Test-Path $regAsm)) {
    throw "RegAsm.exe not found. .NET Framework 4.8 is required."
}

& $regAsm (Join-Path $destination "PartCode.PdmAddIn.dll") /codebase
if ($LASTEXITCODE -ne 0) {
    throw "RegAsm failed with exit code $LASTEXITCODE."
}

Add-Type -AssemblyName System.Security
$entropy = [System.Text.Encoding]::UTF8.GetBytes("PartCode.PdmAddIn.v1")
$secret = [System.Text.Encoding]::UTF8.GetBytes($ApiKey)
$protected = [System.Security.Cryptography.ProtectedData]::Protect(
    $secret,
    $entropy,
    [System.Security.Cryptography.DataProtectionScope]::LocalMachine)
$protectedBase64 = [Convert]::ToBase64String($protected)

$configDirectory = Join-Path $env:ProgramData "PartCode"
New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
$configPath = Join-Path $configDirectory "pdm-connector.json"

$config = [ordered]@{
    baseUrl = $BaseUrl.TrimEnd("/")
    apiKeyProtected = $protectedBase64
    documentType = $DocumentType
    targetVariable = $TargetVariable
    sourceVariables = [ordered]@{
        Description = "description"
        Material = "material"
        Family = "family"
    }
}

$config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8

# The key is machine-protected, but the config should not be world-writable.
& icacls $configDirectory /inheritance:r | Out-Null
& icacls $configDirectory /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-545:(OI)(CI)RX" | Out-Null

Write-Host ""
Write-Host "PartCode PDM add-in installed."
Write-Host "  DLL:    $(Join-Path $destination 'PartCode.PdmAddIn.dll')"
Write-Host "  Config: $configPath"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open SOLIDWORKS PDM Administration."
Write-Host "  2. Right-click Add-ins and create a new add-in."
Write-Host "  3. Select the DLL above and enable it for the vault."
Write-Host "  4. Restart the PDM client / Explorer."
Write-Host "  5. Select a file in the vault, right-click, and choose 'PartCode: assign code...'."

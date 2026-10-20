param(
    [string]$DataDirectory = "$env:LOCALAPPDATA\FacultyRegister",
    [string]$HostName = 'localhost',
    [string]$BindAddress = '127.0.0.1',
    [int]$HttpPort = 8000,
    [int]$HttpsPort = 8443,
    [Parameter(Mandatory = $true)][string]$CaddyPath,
    [Parameter(Mandatory = $true)][string]$CaddySha256,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$projectPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectPath
$dataPath = [System.IO.Path]::GetFullPath($DataDirectory)
if (Test-Path -LiteralPath $dataPath) {
    $contents = @(Get-ChildItem -LiteralPath $dataPath -Force)
    if ($contents.Count -gt 0 -and -not (Test-Path -LiteralPath (Join-Path $dataPath 'register.sqlite3'))) {
        throw 'Use an empty application data directory or an existing Faculty Register installation.'
    }
}
$caddyBinary = (Resolve-Path -LiteralPath $CaddyPath).Path
if ((Get-FileHash -LiteralPath $caddyBinary -Algorithm SHA256).Hash -ne $CaddySha256) { throw 'Caddy checksum mismatch.' }
New-Item -ItemType Directory -Force -Path $dataPath | Out-Null
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $dataPath /inheritance:r /grant:r "${identity}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' 'BUILTIN\Administrators:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict data-directory access.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
$pythonExe = Join-Path $projectPath '.venv\Scripts\python.exe'
& $pythonExe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$secretPath = Join-Path $dataPath 'secret.key'
if (-not (Test-Path -LiteralPath $secretPath)) {
    & $pythonExe -c 'import secrets,sys; from pathlib import Path; Path(sys.argv[1]).write_text(secrets.token_urlsafe(64))' $secretPath
}
$env:REGISTER_DATA_DIR = $dataPath
$env:REGISTER_SECRET_KEY = [System.IO.File]::ReadAllText($secretPath).Trim()
$env:REGISTER_ENV = 'production'
$env:REGISTER_ALLOWED_HOSTS = $HostName
$env:REGISTER_TRUST_PROXY = '1'
if (Test-Path -LiteralPath (Join-Path $dataPath 'register.sqlite3')) {
    & $pythonExe manage.py backup_registers
    if ($LASTEXITCODE -ne 0) { throw 'Pre-upgrade backup failed. Setup stopped.' }
}
foreach ($arguments in @(@('manage.py','migrate','--noinput'), @('manage.py','collectstatic','--noinput'), @('manage.py','check','--deploy'), @('manage.py','bootstrap_admin','--if-missing'))) {
    & $pythonExe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Setup check failed. Inspect output above.' }
}
$caddyVersion = (& $caddyBinary version | Out-String).Trim()
[ordered]@{ hostname=$HostName; bind_address=$BindAddress; http_port=$HttpPort; https_port=$HttpsPort;
    caddy_path=$caddyBinary; caddy_sha256=$CaddySha256; caddy_version=$caddyVersion } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dataPath 'runtime.json') -Encoding UTF8
& $pythonExe -c 'import sys; from pathlib import Path; from operations.runtime import runtime_config; runtime_config(Path(sys.argv[1])); print("Configuration checked.")' $dataPath
if ($LASTEXITCODE -ne 0) { throw 'Runtime configuration is invalid.' }
Write-Host 'Setup complete. Use start.ps1. Network firewall access and client certificate trust require separate configuration.'

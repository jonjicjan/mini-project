param(
    [string]$Python = 'py',
    [switch]$SkipAdministrator
)
$ErrorActionPreference = 'Stop'
if ($env:REGISTER_ENV -and $env:REGISTER_ENV -ne 'development') {
    throw 'This script is for development. Production deployment is not implemented yet.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        if ($Python -eq 'py') { & py -3.12 -m venv .venv }
        else { & $Python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & ./.venv/Scripts/python.exe -m pip install -r requirements-dev.lock
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & ./.venv/Scripts/python.exe manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
    & ./.venv/Scripts/python.exe manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Application checks failed.' }
    if (-not $SkipAdministrator) {
        & ./.venv/Scripts/python.exe manage.py bootstrap_admin
        if ($LASTEXITCODE -ne 0) { throw 'Administrator setup did not complete. Existing installations can use -SkipAdministrator.' }
    }
    Write-Host 'Development setup complete. Run scripts/windows/start-development.ps1.'
}
finally { Pop-Location }

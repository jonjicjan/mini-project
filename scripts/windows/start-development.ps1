param(
    [ValidateRange(1024,65535)][int]$Port = 8000,
    [switch]$SetupAdministrator
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Run setup-development.ps1 first.' }
    if ($env:REGISTER_ENV -and $env:REGISTER_ENV -ne 'development') { throw 'This launcher is for local development only.' }
    if ($SetupAdministrator) {
        & ./.venv/Scripts/python.exe manage.py bootstrap_admin --if-missing
        if ($LASTEXITCODE -ne 0) { throw 'Administrator setup did not complete.' }
    }
    Write-Host "Local development address: http://127.0.0.1:$Port"
    & ./.venv/Scripts/python.exe manage.py runserver "127.0.0.1:$Port" --noreload
    if ($LASTEXITCODE -ne 0) { throw 'The development server stopped with an error.' }
}
finally { Pop-Location }

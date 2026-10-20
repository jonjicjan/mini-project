param([string]$DataDirectory = "$env:LOCALAPPDATA\FacultyRegister")
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath (Join-Path $DataDirectory 'runtime.json') -Raw | ConvertFrom-Json
$url = "https://$($config.hostname):$($config.https_port)/health/"
$response = Invoke-WebRequest -Uri $url -UseBasicParsing
if ($response.StatusCode -ne 200) { throw 'HTTPS health check failed.' }
Write-Host "HTTPS health check passed: $url"
Write-Host 'Still verify login from a second PC, restart persistence, backup restoration and physical printing.'

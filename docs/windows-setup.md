# Windows installation and operations

The production launcher and checks are supplied, but this installation has not yet been activated on a college host. The hostname/private IP, hosting account, approved Caddy binary, certificate trust and backup destination still need to be selected. Do not call an unperformed second-PC or printer check successful.

## Prepare the host

Use a supported Python 3.12 installation and a stable Windows account. The default persistent data directory is `%LOCALAPPDATA%\FacultyRegister`; program upgrades must retain it. Setup restricts that directory to the current account, SYSTEM and Administrators. Use an empty app directory or an existing Faculty Register database; do not point setup at a general documents folder.

Obtain a Windows Caddy release from its [official releases](https://github.com/caddyserver/caddy/releases). Verify the release checksum from that source, unpack it into a stable program directory, and supply the SHA256 of the verified executable to setup. Setup records the executable version and hash; runtime refuses a changed binary. No unverified binary is downloaded automatically.

The following defaults bind HTTPS only to this computer:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/setup.ps1 -CaddyPath 'C:\FacultyRegisterTools\caddy.exe' -CaddySha256 'VERIFIED_EXECUTABLE_SHA256' -Python 'C:\Path\To\python.exe'
powershell -ExecutionPolicy Bypass -File scripts/windows/start.ps1
```

For campus access, pass `-HostName 'faculty-register.college.local' -BindAddress 'PRIVATE_HOST_IPV4'` to setup after the institution supplies the DNS name and private address. The ports default to loopback Waitress 8000 and Caddy HTTPS 8443; use `-HttpPort` / `-HttpsPort` to change them. Stop the development server if it already occupies port 8000. The runtime refuses unspecified/public bind addresses.

Setup installs locked dependencies, makes a pre-upgrade database backup, migrates, collects static files, runs Django deployment checks and prompts for an administrator if needed. It creates a random installation secret without displaying it. Existing local development data under `var/` is not silently moved into a new installation: select the intended data directory explicitly or restore a verified backup into the new installation using maintenance commands.

## HTTPS and network access

Caddy uses an internal certificate authority in this configuration. Its data is kept separately under the protected data directory's `caddy-data/` folder. See the [Caddy TLS documentation](https://caddyserver.com/docs/caddyfile/directives/tls). Only distribute its public root certificate to approved client PCs; never distribute the CA private key.

Locate the generated public `root.crt` beneath `caddy-data/caddy/pki/authorities/local/`. Verify the certificate fingerprint with the administrator through an approved channel. On each Windows client, an administrator can import that public root:

```powershell
certutil -addstore -f Root 'C:\ApprovedTransfer\root.crt'
```

Name resolution must point the configured hostname to the private host IP. If institutional certificates are required instead of an internal CA, arrange them before activation and adapt the generated TLS configuration; the current generator specifically uses `tls internal`.

Firewall changes are not automatic. After institutional approval, an administrator can allow only the private network/subnet, replacing the placeholders:

```powershell
New-NetFirewallRule -DisplayName 'Faculty Register HTTPS' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -Profile Private -RemoteAddress 'APPROVED_CAMPUS_SUBNET'
```

Do not expose port 8000. Waitress listens on loopback and trusts forwarding headers only from loopback Caddy, following [Waitress proxy guidance](https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html). Caddy serves only the collected `static/` directory and proxies application requests; private databases, backups and exports are never a public file-server root.

## Start, stop and startup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/start.ps1
powershell -ExecutionPolicy Bypass -File scripts/windows/stop.ps1
powershell -ExecutionPolicy Bypass -File scripts/windows/install-startup.ps1
```

Pass the same `-DataDirectory` to every script when using a custom path. Startup installation is optional and runs when the selected Windows account signs in; it is not a boot service for an unattended host. The supervisor holds an exclusive lock, stops its child servers when either fails, writes server output to `logs/runtime.log`, and runs one daily backup scheduler. A second supervisor or restore process cannot acquire the same lock. After a forced machine/process termination, check that no orphaned server still uses the database before maintenance.

## Backup and restore

The administrator's browser has **System backups → Create verified backup** and protected download links. A SQLite online backup includes accounts, student/lesson data, schedules, attendance, rules, marks and issued DOCX bytes in one consistent database. ZIP manifests contain the application/backup format, migration list and SHA256. Configuration secrets and CA keys are excluded and need a separate protected host backup.

To use management commands for a production installation, set the environment without printing the secret:

```powershell
$registerData = Join-Path $env:LOCALAPPDATA 'FacultyRegister'
$registerConfig = Get-Content -LiteralPath (Join-Path $registerData 'runtime.json') -Raw | ConvertFrom-Json
$env:REGISTER_ENV = 'production'
$env:REGISTER_DATA_DIR = $registerData
$env:REGISTER_ALLOWED_HOSTS = $registerConfig.hostname
$env:REGISTER_SECRET_KEY = [IO.File]::ReadAllText((Join-Path $registerData 'secret.key')).Trim()
$env:REGISTER_TRUST_PROXY = '1'
.\.venv\Scripts\python.exe manage.py backup_registers
```

For restore, stop the supervisor and all development/database processes first, then:

```powershell
.\.venv\Scripts\python.exe manage.py restore_registers 'C:\ApprovedBackups\register-TIMESTAMP.zip' --maintenance
```

Restore checks archive paths, size, format, checksum, database integrity and migration compatibility before replacing the database. It creates a verified pre-restore copy under `recovery/`, stages the replacement, deletes restored login sessions, and uses an atomic file replacement. A file-lock or validation failure leaves the previous database selected. Existing WAL sidecars cause a refusal; stop database users and checkpoint them rather than deleting them. A backup from another schema must first be restored into a matching isolated installation and upgraded there.

Keep at least one separate copy on approved storage: local daily backups alone do not protect against host-disk loss. Daily pruning retains the latest 30 dates of validated successful copies; damaged archives are not treated as successful replacements. Review runtime backup errors and periodically restore into a disposable installation.

## Acceptance checks

Run `check-install.ps1` after installing the trusted certificate and starting the app. It verifies HTTPS `/health/` without disabling certificate verification. Then independently verify login from a second college PC, account isolation, saving and restart persistence, an administrator backup and disposable restore, and custom-size physical printing. Record the actual host, Word/printer, Caddy version/checksum, certificate fingerprint, client test and recovery result. These host/hardware acceptance steps remain pending until performed.

The source package includes the manual workflows. Later refinements from the wider plan—shared reusable marking/timetable templates, autosave recovery, multi-register calendar reconciliation and a calendar day/week/month interface—are not represented as completed by this manual release.

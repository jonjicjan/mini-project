# Implementation verification

## Manual workflow release — 5 October 2026

```text
.venv/Scripts/python.exe -m pytest -q --browser chromium --browser-channel msedge --tb=short
88 passed in 66.60s

.venv/Scripts/python.exe manage.py check
System check identified no issues (0 silenced).

.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
No changes detected

.venv/Scripts/python.exe -m ruff check .
All checks passed!
```

The production profile also passed `manage.py check --deploy` with a disposable data directory, ephemeral secret, explicit localhost and trusted-proxy setting. All eight Windows PowerShell scripts passed parser checks. Caddy, scheduled startup, certificate trust and LAN access remain unverified on an actual deployment host.

New coverage includes atomic paste imports and rollback, stable identities, historical dates and time confirmation, ownership, late-joiner attendance, explicit absence/completion, cancelled and future classes, stable schedule rebuilding and stale previews, holiday conflicts, test replacement, assessment formulas and rounding, missing/absent marks, immutable private Word exports and export retries. Backup tests cover integrity, restore/recovery, session invalidation, corrupt/unsafe archives, host locking, simulated replacement failure, retention and daily backup recovery.

A real Edge workflow exercised manual student, lesson and class entry, absence and completion, saved reload, marking rules, marks and Word download. Desktop and 390px mobile layouts were checked. The generated export from synthetic saved application records rendered to 12 pages in Microsoft Word; all 12 pages were visually inspected without clipping. Physical printing remains pending.

The existing local database was backed up to `var/pre-upgrade-backups/` before applying the new migrations. No synthetic test records were inserted into that database. The upgraded local server returned HTTP 200 for `/health/` and `/login/` on port 8000. See [implementation status](implementation-status.md) for remaining original-design features and institutional acceptance work.

The sections below preserve earlier milestone evidence; their pending-work lists describe the earlier dates, not the current release.

## Booklet prototype — 2 October 2026

Task 3 now includes a pure snapshot-to-DOCX renderer, a leaf planner, synthetic fixture, development command and print guide. The fixture contains no photographed student data. The command does not read or mutate the application's database.

The geometry tests first failed as expected because `exports` did not exist. The completed implementation passed the full regression suite:

```text
.venv/Scripts/python.exe -m pytest -q --browser chromium --browser-channel msedge --tb=short
55 passed in 34.07s

.venv/Scripts/python.exe manage.py check
System check identified no issues (0 silenced).

.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
No changes detected
```

Geometry coverage includes 0/20/21/61 students, 0/75/76/151 sessions, exact once-only column coverage, invalid counts, full/half page sizes within one twip, 20 non-splitting body rows per panel, red absence runs, blank signature spaces, no embedded photographs, oversized-name warnings, unchanged input snapshots, and a 36-section DOCX for 21 students and 76 sessions. The latter also checks that unused rows remain blank and assessments appear only in the last session set.

The supplied sample generated without fit warnings. The initial Word render exposed signature rows overflowing despite valid XML; compatibility mode and vertical cell padding were corrected. Microsoft Word 16.0 build 16.0.20430 then rendered the final sample to exactly 12 pages. Every page was inspected at native 144-dpi PNG size; no clipping, blank overflow pages or displaced signatures remained. Full/half attendance body rows align. The timetable uses the photographed weekly matrix structure, including break columns. See [print guide](print-guide.md) for the exact commands, measured dimensions and renderer fallback.

The packaged LibreOffice renderer was attempted and its missing `soffice.exe` diagnosed before using Word. DOCX generation itself has no Word/LibreOffice runtime dependency. Actual paper feed, duplex pairing, binding and official logo artwork remain unverified. Immutable live-data snapshots and protected downloads are later Task 10 work.

## Foundation — 1 October 2026

## Implemented scope

Accounts, owned course registers, explicit saves, archive/restore, operation receipts, audit records and local development setup. This is the functionality of Tasks 1–2; it is not verification of the complete attendance-register application.

## Environment and dependencies

- Windows host; Python 3.12.14.
- Django 5.2.17; SQLite; development dependency versions are recorded in `requirements-dev.lock`.
- Real browser workflow tests used headless Microsoft Edge through Playwright's Chromium driver.
- The initial development environment was created in `.venv`. A separate fresh `.venv-check` was created and all dependencies installed from the exact development lock; the complete test suite was then run from that environment.
- Tests use synthetic identities and their own temporary on-disk SQLite database. No photographed student records are used. No administrator account was created in the ordinary development database.

## Actual command results

```text
.venv-check/Scripts/python.exe -m pytest -q --browser chromium --browser-channel msedge --tb=short
31 passed in 14.65s

.venv-check/Scripts/python.exe -m pip check
No broken requirements found.

.venv-check/Scripts/python.exe manage.py check
System check identified no issues (0 silenced).

.venv-check/Scripts/python.exe manage.py makemigrations --check --dry-run
No changes detected

.venv-check/Scripts/python.exe -m ruff check .
All checks passed!

git diff --check
No whitespace errors. Git reported the host's normal LF-to-CRLF conversion notices.
```

`manage.py migrate --noinput` successfully created all initial database tables. `manage.py check --deploy` also reported no issues under the production settings profile, with an explicit disposable data location, an ephemeral secret, an example internal hostname and trusted-proxy settings. This was a configuration check; no Caddy server, LAN TLS certificate or second-PC connection was deployed or verified.

The actual Windows development launcher was started with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/windows/start-development.ps1 -Port 8765
```

It started Django 5.2.17 successfully on loopback. `/health/` returned HTTP 200 with `{"status":"ok"}` and `/login/` returned HTTP 200. The smoke-test server was stopped after verification.

## Behaviours exercised

- Anonymous redirects; successful/failed login; POST-only logout; blocked disabled accounts; CSRF rejection; safe redirect targets.
- Login throttling by username and source address, including expiry.
- Administrator-only faculty creation, weak-password/duplicate-username rejection, password reset, disable/enable, session invalidation and audit redaction.
- Interactive first-administrator bootstrap, mismatched-password rejection and refusal to duplicate an existing administrator.
- Ownership checks in both services and HTTP requests, including protected JSON changes and absent foreign-register information.
- Register creation, editing, search/list rendering, date validation, archive/restore and archived-record edit protection.
- Repeated operation IDs return their original result. Different payloads or scopes cannot reuse receipts. Repeated archive submissions cannot restore the register accidentally.
- Transaction rollback removes partial changes, audit events and receipts together. Busy writes retry at most twice before a retryable failure.
- Two independent SQLite connections submitting the same revision yield exactly one successful save and one conflict.
- Revoked accounts and revoked administrator rights are checked again inside the write transaction.
- Browser workflow: real login, course creation, saved reload, stale-tab conflict with attempted values retained, archive/restore on mobile, administrator account creation/password reset and a foreign-register 404.

## Visual inspection

The login, dashboard and register editor were inspected at 1440px width. The dashboard was inspected at 390px width; browser assertions also checked horizontal fit in the mobile editor. A mobile archive-control visibility issue found by the workflow was corrected and the workflow passed afterward.

Generated screenshots are local ignored artifacts under `artifacts/screenshots/`:

- `login-desktop.png`
- `dashboard-desktop.png`
- `dashboard-mobile.png`
- `register-desktop.png`

The browser test session explicitly permits synchronous Django fixture operations while Playwright's sync API holds its event loop in the test thread. This setting exists only in the browser test fixture; it is not enabled in application settings. The live server uses a separate database connection.

## Remaining acceptance work

Tasks 4–12, standalone-host setup, production supervision, backup/restore, physical Word/printer assembly, official logo artwork, a second-PC HTTPS login and independent review remain pending. The local launcher and successful checks do not make this a production-ready application. No Git commit or deployment was made.

Implementation references: Django's [authentication documentation](https://docs.djangoproject.com/en/5.2/topics/auth/default/) and [SQLite transaction guidance](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes).

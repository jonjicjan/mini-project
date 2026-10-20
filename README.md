# Faculty Attendance Register

This repository contains the approved design, implementation plan, 24 reference photographs, and a working manual-entry application. Faculty can maintain separate registers by department, section and subject, with student and lesson entry/paste imports, timetables, scheduling, holidays, attendance, assessment rules and marks, and Word exports from saved records.

**Ready for local workflow use and evaluation; college production activation is pending.** Verified database backup/restore and Windows deployment scripts are included. Hosting, HTTPS trust, second-PC access and physical printer acceptance still need checking on the intended college setup. Read the [faculty guide](docs/faculty-guide.md), [Windows setup guide](docs/windows-setup.md), [implementation status](docs/implementation-status.md) and [verification evidence](docs/verification.md).

## Run the current application on Windows

For a new checkout, install Python 3.12, open PowerShell in the project directory, and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/setup-development.ps1
powershell -ExecutionPolicy Bypass -File scripts/windows/start-development.ps1
```

Setup prompts for the first administrator's username and password; there are no default credentials. If Python is not registered with the `py` launcher, pass its executable path with `-Python`. For subsequent setup runs, use `-SkipAdministrator`.

The implementation session has already created `.venv`, installed dependencies and migrated the local development database on this machine. **Double-click `Start Faculty Register.cmd`** to create your initial administrator through local prompts and start the app. Alternatively, finish first-time setup here with:

```powershell
.\.venv\Scripts\python.exe manage.py bootstrap_admin
powershell -ExecutionPolicy Bypass -File scripts/windows/start-development.ps1
```

Open **http://127.0.0.1:8000/**. Sign in as the administrator and use **Faculty accounts** to create logins. Each faculty member can create, edit, search, archive and restore their own registers. Open a register and choose **Students, attendance & marks** for its workflow tabs. Saves are explicit; attendance completion is a separate action. Stop a foreground development server with Ctrl+C.

Local development records are stored in `var/register.sqlite3`, including issued Word documents. The generated development secret is also in ignored `var/`. Keep this directory to preserve accounts and registers across restarts. Tests use separate temporary databases and synthetic accounts; no photographed student records are imported. Setup prompts for administrator credentials if an administrator does not already exist.

For local administrator password recovery:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword YOUR_ADMIN_USERNAME
```

## Developer checks

Generate the 12-page Word print prototype with synthetic data:

```powershell
.\.venv\Scripts\python.exe manage.py render_booklet_fixture --output artifacts/booklet-sample.docx
```

See the [print guide](docs/print-guide.md) for page order, half-leaf assembly, fit warnings and pending printer calibration. This command does not read or change saved registers.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration -q
.\.venv\Scripts\python.exe -m pytest tests/unit -q
.\.venv\Scripts\python.exe -m pytest tests/browser -q --browser chromium --browser-channel msedge
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m ruff check .
```

Browser checks can use installed Microsoft Edge as shown. For Playwright's bundled Chromium, first run `python -m playwright install chromium` in the environment and omit `--browser-channel msedge`. Runtime dependencies are pinned in `requirements.lock`; development and testing dependencies are pinned in `requirements-dev.lock`. The development launcher is local-only; the separate [Windows deployment guide](docs/windows-setup.md) describes Waitress/Caddy HTTPS setup.

## Start here

1. Read the [approved design](docs/superpowers/specs/2026-10-01-attendance-register-design.md) for the required behaviour and acceptance criteria.
2. Follow the [implementation plan](docs/superpowers/plans/2026-10-01-attendance-register.md), which divides the work into 12 testable tasks with files, interfaces, checks and milestones.
3. Inspect the photographs at the repository root before designing the Word output. Numbered images follow the supplied page order, but some show folded or overlapping leaves.

The `docs/superpowers/` path preserves the original document location. The plan is written for student developers and requires no particular AI tool.

## Original design scope

The manual release implements the core record workflows below. Shared timetable versions, reusable marking templates, calendar views and resilient autosave remain additional work; see the implementation status for the exact boundary.

- One Windows PC hosts the application; faculty access it through browsers on the college network.
- Each faculty member has a login and centrally saved registers.
- Faculty paste lesson plans, student USNs and names, marks and timetable data into editable tables.
- A calendar and student grid record absences, calculate running attendance, and support timetable versions and unplanned holidays.
- Three dated internal tests count as attendance sessions. Their attendance percentages are cumulative from the start through each test date.
- Configurable marking rules define maximum marks, percentage contributions, averaging or best-N selection, and final rounding.
- Word output reproduces the supplied booklet's interior sheets, including the half-width attendance leaves, assessment records and timetable insert.

## Print requirements

| Item | Requirement |
| --- | --- |
| Full page | 210 mm wide by 307 mm high |
| Half-page attendance leaf | 105 mm wide by 307 mm high |
| Student rows | 20 per attendance block |
| Base attendance capacity | 75 session columns, with continuation when needed |
| Covers | Reuse the existing physical covers; export interior sheets only |
| Presence | Running number of classes attended |
| Absence | Red A |

The custom height exceeds standard A4. Verify actual-size printing and half-page assembly on the intended Windows printer; do not scale the format to A4. Preserve historical attendance when dates change, and never transfer an absence automatically to a replacement class.

## Photograph guide

| Files | Content |
| --- | --- |
| `cover page.JPG` | Existing outer cover and metadata reference |
| `inside cover page.JPG` | Attendance-marking instructions |
| `page2.JPG`, `IMG_1640.JPG`, `IMG_1641.JPG` | Three lesson-plan pages |
| `IMG_1642.JPG` to `IMG_1647.JPG` | Attendance and assessment sheets for the first student block |
| `IMG_1648.JPG` to `IMG_1653.JPG` | Second student block |
| `IMG_1654.JPG` to `IMG_1659.JPG` | Third student block |
| `inside of back cover.JPG` | Faculty timetable reference |

Use synthetic student records for tests and demonstrations. The photographs are layout references, not application seed data.

## Student milestones

1. **Tasks 1 to 3:** accounts, saved registers and an early booklet print sample.
2. **Tasks 4 to 6:** pasted data, effective timetables, holidays and test scheduling.
3. **Tasks 7 to 9:** attendance grid, reliable saving and configurable marks.
4. **Tasks 10 to 12:** complete Word export, backup and restore, and Windows deployment.

For each task, nominate an implementer and a reviewer. Demonstrate the completed workflow and a physically assembled booklet to the faculty supervisor before the application is used for live records.

# Faculty Attendance Register Implementation Plan

> **For student developers:** Build this application task by task from the approved design. Each task identifies files, service contracts, implementation steps and evidence of correctness. Check a step only after completing and verifying it. This repository currently supplies the plan and reference material; application development is assigned to the student team.

**Goal:** Build the approved Windows-hosted college-network application that saves each faculty member's registers and produces replacement Word booklet inserts.

**Architecture:** Django owns accounts, persistence and transactional changes on one Windows host, using a local SQLite database. Focused browser JavaScript adds paste previews, attendance selection and reliable autosaving; shared calculation services supply both the screens and DOCX exports. Waitress serves the application behind a local Caddy HTTPS front end.

**Tech Stack:** Python 3.12 or newer within Django's supported versions, Django 5.2, SQLite, Waitress, Caddy, python-docx, local CSS and JavaScript; pytest, pytest-django and pytest-playwright for automated checks. Resolve compatible patch releases and pin them at implementation, including development dependencies.

**Spec:** [Approved design](../specs/2026-10-01-attendance-register-design.md), approved on 1 October 2026.

## Global Constraints

- Full pages measure 210 mm wide by 307 mm high; half-pages measure 105 mm wide by 307 mm high.
- The attendance format accommodates 20 student rows per block and 75 numbered session columns.
- Use structured copy and paste and direct editing instead of document uploads or document extraction.
- Store dates as calendar dates in Asia/Kolkata. Store audit timestamps separately in UTC.
- Each session has a permanent identifier independent of its displayed number, date or topic.
- A replacement class is a new session with unmarked attendance; it does not inherit the old session's absent students.
- Each test is one attendance session, and each test attendance percentage is cumulative from the start through that test date, including the test session.
- The enabled contributions must total exactly 100 percent using decimal arithmetic.
- Missing required marks keep the result pending; never rescale remaining weights to hide a missing assessment.
- Keep transactions short and handle busy writes with bounded retries.
- Routine faculty use requires only a browser; the host PC and college network must be available.
- Use synthetic students and marks for development and demonstrations. The original register photographs are included in the teaching repository at the user's request as layout references; do not turn their handwritten student information into application seed data.
- Do not reproduce handwritten signatures or prepopulate real student records from the reference photographs.
- Do not substitute a generic A4 report when those checks remain unfinished.

## Review Focus

- Retried saves after a lost response must not duplicate an operation or falsely report unsaved work as saved. Pin this in Tasks 2 and 8.
- Copying a revised roster with blank marks, reordered USNs or a late student must not erase marks, shift attendance or invent historical presence. Pin this in Tasks 4 and 9.
- A retroactive timetable change affecting several registers and a test on a holiday must preserve completed events and expose every conflict. Pin this in Tasks 5 and 6.
- Long names, a 21st student, a 76th session and mixed page widths must preserve row alignment and running counts. Pin this in Tasks 3 and 10.
- A full disk, damaged backup or Windows process holding the database open must fail safely, retaining the working database. Pin this in Tasks 11 and 12.

---

## Student development workflow

This is one cohesive build: accounts, calendars, attendance, marks and print output share the same saved register. The tasks are independently testable increments of that application, not separate products. Work through them in order. Physical print calibration can proceed alongside later development; an unavailable Windows machine or printer does not prevent completing portable code and automated checks, but those hardware checks must remain explicitly unverified.

The repository contains the approved design, this plan and 24 original reference photographs at its root. The photographs retain their supplied filenames and order. Clone the repository and create a feature branch for each task. Keep the reference images unchanged. Use a configurable `REGISTER_REFERENCE_DIR` pointing to the repository root when development tools need them; never hard-code one developer's machine path.

Create an isolated Python virtual environment with a supported interpreter, using Python 3.12 as the baseline. Commands below use `python` after that environment is active; the Windows launcher uses its own `.venv\Scripts\python.exe`. On Windows, the initial setup commands are `py -3.12 -m venv .venv` and `.venv\Scripts\Activate.ps1`. Check interpreter and library compatibility before generating the dependency lock.

Student developers will create the application files described below; those files do not exist yet. For each task, first write the behaviour checks, confirm the expected failure, implement the change, run the checks and request a teammate's review before merging. Record requirements questions and changes with the faculty supervisor rather than silently changing the approved design.

Use pytest-playwright with Chromium for repeatable browser tests and pytest-django's live server for an isolated test application. Install the test browser with `python -m playwright install chromium` in the development environment. Render DOCX files to PDF or page images using Word or LibreOffice for visual inspection; additionally verify final physical output in Microsoft Word on the intended Windows printer. No Codex-specific tools or skills are required for students to follow this plan.

## File structure and contracts

Create the following focused modules. Add normal package markers, app configuration and migration directories as part of the task that introduces an application.

| Paths | Responsibility |
| --- | --- |
| `manage.py`, `pyproject.toml`, `requirements.in`, `requirements.lock`, `requirements-dev.in`, `requirements-dev.lock`, `.gitignore` | Project entry point, dependency locking and local-data exclusions |
| `config/settings.py`, `config/urls.py`, `config/wsgi.py` | Environment-specific settings and HTTP entry points |
| `core/errors.py`, `core/mutations.py`, `core/models.py`, `core/dates.py` | Structured errors, revision checks, request receipts, audit events and date parsing |
| `accounts/views.py`, `accounts/services.py`, `accounts/urls.py`, `accounts/models.py` | Authentication, login throttling, account administration |
| `registers/models.py`, `registers/services.py`, `registers/paste.py`, `registers/views.py`, `registers/urls.py` | Registers, students, lessons, paste validation and editors |
| `scheduling/models.py`, `scheduling/slots.py`, `scheduling/rebuild.py`, `scheduling/reconcile.py`, `scheduling/tests_calendar.py`, `scheduling/views.py`, `scheduling/urls.py` | Versioned timetables, holidays, sessions and reconciliation |
| `attendance/models.py`, `attendance/services.py`, `attendance/calculations.py`, `attendance/views.py`, `attendance/urls.py` | Explicit attendance records, completion and summaries |
| `assessments/models.py`, `assessments/rules.py`, `assessments/calculations.py`, `assessments/services.py`, `assessments/views.py`, `assessments/urls.py` | Marking templates, scores and USN-based marks entry |
| `exports/geometry.py`, `exports/leaves.py`, `exports/docx_render.py`, `exports/snapshot.py`, `exports/models.py`, `exports/views.py`, `exports/urls.py` | Physical booklet layout, consistent saved snapshots and downloads |
| `operations/backups.py`, `operations/runtime.py`, `operations/views.py`, `operations/urls.py` | Backups, maintenance, restoration and process lifecycle |
| `templates/base.html`, `templates/accounts/`, `templates/registers/`, `templates/scheduling/`, `templates/attendance/`, `templates/assessments/`, `templates/exports/`, `templates/operations/` | Server-rendered pages alongside their owning task |
| `static/css/app.css`, `static/js/api.js`, `static/js/autosave.js`, `static/js/paste.js`, `static/js/attendance.js`, `static/js/calendar.js`, `static/js/assessments.js` | Local browser assets; no CDN or client-side source of truth |
| `tests/conftest.py`, `tests/factories.py`, `tests/unit/`, `tests/integration/`, `tests/browser/` | Synthetic fixtures and focused verification |
| `scripts/windows/`, `docs/windows-setup.md`, `docs/print-guide.md`, `docs/verification.md` | Windows deployment and delivery evidence |

Model identities are UUIDs except Django user IDs. Money-like quantities, scores and percentages use decimal strings at API boundaries and `Decimal` in calculations. Never calculate authoritative marks in JavaScript.

Every mutation endpoint takes `expected_revision` and a UUID `request_id` in addition to its form-specific data. A successful response is `{revision, request_id, data, warnings}`. Validation errors are HTTP 422 with `{code, message, field_errors}`; stale edits are HTTP 409 with current revision and attempted/current values; unauthorised owned-object access is HTTP 404; a retryable storage failure is HTTP 503. Reusing an operation ID with a different payload is a conflict, not an accepted retry.

Place ownership checks at service boundaries. Browser views pass the authenticated actor; internal work such as backup uses explicit administrative services. Store saved snapshots as versioned JSON using strings for dates, UUIDs and decimals. A final export is generated from a captured snapshot, never a succession of live queries during DOCX rendering.

## Task 1: Runnable application and account login

**Files:** Create project configuration, `accounts/` modules, `templates/base.html`, `templates/accounts/login.html`, `templates/accounts/manage.html`, `static/css/app.css`, `tests/conftest.py`, `tests/integration/test_accounts.py`, and `README.md`.

**Interfaces:** Consume Django's user model and session framework. Produce `create_faculty(actor, *, username: str, display_name: str, temporary_password: str) -> User`, `reset_faculty_password(actor, user_id: int, password: str) -> None`, and `set_faculty_active(actor, user_id: int, active: bool) -> None` in `accounts/services.py`. Login is `/login/`, logout is POST `/logout/`, account administration is `/admin/faculty/`, and `/health/` returns only service availability.

- [ ] **Step 1:** Create the virtual environment and the minimal test/configuration shell. Add Django 5.2, Waitress, python-docx and their dependencies; add pytest, pytest-django, pytest-playwright and pip-tools to the development requirements. Resolve and commit exact lock files. Configure a temporary SQLite file for tests and a separately configured persistent directory for deployment. Ignore private runtime data, environments and generated files without ignoring or changing the supplied tracked photographs.
- [ ] **Step 2:** Write account tests with the following assertions, using synthetic users:

```python
assert anonymous.get('/').status_code == 302
assert faculty.get('/admin/faculty/').status_code == 403
assert admin_create_faculty('teacher1').is_active is True
assert login('teacher1', 'incorrect').status_code == 200
assert login('teacher1', 'correct-password').status_code == 302
assert session_after_password_reset.get('/').status_code == 302
assert disabled_faculty_can_login() is False
```

The local test helpers perform requests rather than bypassing login. Also assert CSRF rejection and the configured lockout response after five failed logins in fifteen minutes; throttle by username and source address without storing passwords.
- [ ] **Step 3:** Run `python -m pytest tests/integration/test_accounts.py -q`; expect failures for missing application behaviour rather than an incompatible interpreter.
- [ ] **Step 4:** Implement the account service signatures and wire framework login/logout, password reset and active-state checks. Add an administrator bootstrap command that prompts for credentials instead of shipping a default password. Use a minimal dashboard with a clear empty state.
- [ ] **Step 5:** Run the account tests and `python manage.py check`; require passing tests and no system-check errors. Prove the chosen dependency lock installs in a fresh environment.
- [ ] **Step 6:** Commit the explicit files for this task with message `feat: add local application and faculty accounts`.

## Task 2: Owned registers and safe saved changes

**Files:** Create `core/errors.py`, `core/mutations.py`, `core/models.py`, `registers/models.py`, `registers/services.py`, `registers/views.py`, `registers/urls.py`, `templates/registers/list.html`, `templates/registers/setup.html`, `tests/factories.py`, `tests/integration/test_registers.py`, `tests/integration/test_mutations.py` and their migrations. Modify `config/urls.py` and settings.

**Interfaces:** Produce `Register(owner, academic_year, semester, branch, section, subject_code, subject_name, faculty_name, term_start, term_end, revision, archived_at)`. Produce `owned_register(actor, register_id: UUID) -> Register` and `update_register(actor, register_id: UUID, *, expected_revision: int, request_id: UUID, values: dict) -> dict`. `core.mutations.run_mutation(actor, *, scope, expected_revision: int, request_id: UUID, payload: dict, change: Callable[[], dict]) -> dict` provides the shared mutation envelope. `scope` is a saved object with `revision`; all domain mutations use it.

- [ ] **Step 1:** Write tests proving foreign-register reads/edits return 404, an archive preserves records, a valid update increments the revision once, a repeated identical request returns its original result, and a stale or differently reused request ID cannot change data. Assert failed transactions create neither partial data nor success receipts. Create reusable `faculty`, `register_factory` and date-injected fixtures in `tests/factories.py`.
- [ ] **Step 2:** Run `python -m pytest tests/integration/test_registers.py tests/integration/test_mutations.py -q`; expect missing model/service failures.
- [ ] **Step 3:** Implement the models, owned queries and shared mutation service. Store the request receipt and before/after audit event inside the same short transaction as the change. Use SQLite immediate transactions and conditional revision updates; do not depend on `select_for_update`, which has no effect on SQLite. Bound retries to two for transient busy errors; retry the entire uncommitted mutation with the same request ID.
- [ ] **Step 4:** Add register creation, setup, archive and list pages. Require term start not after term end. Create ownership checks for both HTML and JSON paths. Allocate the audit/request models now so later tasks share one mechanism.
- [ ] **Step 5:** Run the two test files, migration checks and `python manage.py check`; require all assertions to pass. A two-connection SQLite test must show that only one same-revision update wins.
- [ ] **Step 6:** Commit `feat: persist owned registers with revision-safe edits`.

## Task 3: Early booklet geometry and sample export

**Files:** Create `exports/geometry.py`, `exports/leaves.py`, `exports/docx_render.py`, `exports/management/commands/render_booklet_fixture.py`, `tests/unit/test_booklet_geometry.py`, `tests/fixtures/booklet_synthetic.json`, and `docs/print-guide.md`.

**Interfaces:** `exports.leaves.plan_leaves(student_count: int, session_count: int) -> list[Leaf]`; define frozen `Leaf(kind: str, width_mm: Decimal, height_mm: Decimal, student_start: int, student_end: int, session_start: int | None, session_end: int | None, side: str)`. `exports.docx_render.render_booklet(snapshot: dict, target: Path) -> list[str]` writes a DOCX and returns fit warnings. The fixture implements the snapshot contract subsequently defined in Task 10 using synthetic records.

- [ ] **Step 1:** Reinspect the photos locally and record the leaf map in `docs/print-guide.md`, distinguishing logical panels, physical sides and overlapping photographs. Map all 75 attendance columns exactly once per student block. Record measured reconstruction margins separately from the authoritative outer dimensions. Do not infer duplex printer feed direction from the photos.
- [ ] **Step 2:** Write geometry tests asserting full-page `(210, 307)` and half-page `(105, 307)` sizes within one DOCX twip, 20 student rows per block, continuation for students 21 and 61, continuation for session 76, and blank signature areas. Parse the DOCX XML to verify red `FF0000` absence text and prevention of split rows. Define a long-name fixture with an explicit fit warning if it cannot fit.
- [ ] **Step 3:** Run `python -m pytest tests/unit/test_booklet_geometry.py -q`; expect missing renderer/geometry failures.
- [ ] **Step 4:** Implement `Leaf`, `plan_leaves`, the page constants and renderer with fixed geometry and proper next-page sections. Reproduce the three lesson-plan pages, roster and continuation leaves, assessment panel and timetable insert; omit all covers. Derive body rows from a shared row-height definition so half-pages align. Source institutional branding from the local references and review it visually; never use signatures or student handwriting as artwork.
- [ ] **Step 5:** Run `python manage.py render_booklet_fixture --output artifacts/booklet-sample.docx`, run the geometry tests, and render all sample pages to PDF or images using Word or LibreOffice. Inspect every resulting page for clipping, blank overflow pages, row alignment and sequence. Adjust the template rather than changing the agreed dimensions. Save the exact rendering command and renderer version in the print guide.
- [ ] **Step 6:** Save the print guide and geometry implementation in commit `feat: reproduce full and half-page booklet geometry`. Make the sample available for printing; record physical Word/printer verification as pending until actually performed. Continue later tasks while awaiting a sample print.

## Task 4: Paste previews and editable roster and lesson plan

**Files:** Create `core/dates.py`, `registers/paste.py`, `static/js/paste.js`, `templates/registers/students.html`, `templates/registers/lessons.html`, `tests/unit/test_paste.py`, `tests/integration/test_imports.py`. Modify register models/services/views/URLs and migrations.

**Interfaces:** Produce `Enrollment(register, usn, name, serial_number, eligible_from, eligible_to, revision)` and `LessonPlanRow(register, original_number, topic, original_date, original_period, reported_execution_date, remarks, revision)`. Produce `parse_date(value: str) -> date`; `preview_paste(text: str, *, table: str, delimiter: str, mapping: dict[str, int]) -> dict` returns `{rows, errors, warnings}` without writes; `apply_paste(actor, register_id: UUID, *, table: str, rows: list[dict], expected_revision: int, request_id: UUID) -> dict` revalidates and saves through Task 2. Table values are `students` and `lessons` here; Tasks 5 and 9 extend parsing for timetable and marks.

- [ ] **Step 1:** Add parameterised tests for ISO and four-digit-year day-first dates, two-digit-year rejection, quoted CSV fields, tabs, empty rows, Unicode names, leading-zero USNs, duplicate USNs and different column mappings. Integration tests must assert that reordered existing USNs update the same enrolments, no import silently deletes a student, and a late enrolment does not receive historical presence.
- [ ] **Step 2:** Run `python -m pytest tests/unit/test_paste.py tests/integration/test_imports.py -q`; expect missing preview/import behaviour.
- [ ] **Step 3:** Implement the date parser and non-mutating previews, including row and column error locations. Implement roster add/update, explicit USN correction and intentional reordering; preserve the enrolment UUID and existing serial order on ordinary import. Store a supplied execution date without creating attendance; Task 5 materialises its session.
- [ ] **Step 4:** Add students and lesson-plan editors with paste areas, mapped preview columns, explicit Apply and row editing. Escape all entered content when rendering. Direct editing and pasted imports must call the same validation services. Provide clear examples and display the accepted date convention.
- [ ] **Step 5:** Run both test files plus the earlier register tests. Confirm a batch containing one invalid row produces no partial import and no revision increment.
- [ ] **Step 6:** Commit `feat: add validated paste entry for students and lessons`.

## Task 5: Versioned timetables and deterministic session scheduling

**Files:** Create `scheduling/models.py`, `scheduling/slots.py`, `scheduling/rebuild.py`, `scheduling/views.py`, `scheduling/urls.py`, `templates/scheduling/timetable.html`, `templates/scheduling/calendar.html`, `static/js/calendar.js`, `tests/unit/test_slots.py`, `tests/integration/test_schedule.py` and migrations. Extend `registers/paste.py` and register queries.

**Interfaces:** Define `TimetableVersion(owner, academic_year, term_key, effective_from, revision)`, `TimetableEntry(version, weekday, period, start_time, end_time, subject_code, section, activity)`, `Holiday(register, start_date, end_date, reason, revision)`, and `Session(register, lesson, kind, scheduled_date, actual_date, period, start_time, end_time, timetable_version, status, fixed, exception_reason, revision)`. Snapshot a conducted session's times so a later timetable edit does not change its historical ordering. Session kinds are `lesson`, `test`, `extra`; statuses are `planned`, `conducted`, `cancelled`. Registers link to a faculty timetable term. Produce `available_slots(register_id: UUID, start: date, end: date) -> list[dict]`, `preview_rebuild(register_id: UUID, *, effective_from: date, today: date) -> dict`, and `apply_rebuild(actor, register_id: UUID, *, preview: dict, expected_revision: int, request_id: UUID) -> dict`. A preview contains its source revision, moves, preserved session IDs, conflict candidates and unplaced lesson IDs.

- [ ] **Step 1:** Write tests for Monday/Wednesday slots, a midterm change to Tuesday/Thursday, two periods on one date, a holiday range, an exceptional Saturday and exhaustion of term slots. Assert rebuilding twice leaves session IDs and row counts unchanged. Create a reported historical execution-date case and assert a conducted session exists with no assumed attendance.
- [ ] **Step 2:** Run `python -m pytest tests/unit/test_slots.py tests/integration/test_schedule.py -q`; expect missing scheduling behaviour.
- [ ] **Step 3:** Implement timetable versions shared across the faculty's term registers, duplicate-effective-date validation and whole-faculty period-overlap checks. Extend paste previews to timetable entries. Version editing must list every affected linked register; no change to other faculty's data is permitted.
- [ ] **Step 4:** Implement slot generation and the rebuild preview. On initial import, materialise past planned dates as unconfirmed sessions for back-entry, and reported execution dates as conducted sessions with unmarked attendance. Preserve these past sessions and completed events during later rebuilds. Place future outstanding topics in stable original order from `max(today, effective_from)`, skipping holidays and occupied fixed slots. Preserve original lesson dates and report unplaced topics instead of extending the term. Apply only a preview whose source revisions still match; all linked-register changes and audit entries belong to one short transaction.
- [ ] **Step 5:** Add timetable version editing and the calendar with day/week/month navigation, period labels, planned versus actual dates and a preview of proposed moves. Provide explicit extra-class, cancellation and holiday controls; changes affecting recorded sessions defer to Task 6 instead of mutating history here.
- [ ] **Step 6:** Run the schedule tests and assert exact expected dates as well as stable IDs. Include a leap-day fixture and an empty timetable case that reports all topics unplaced.
- [ ] **Step 7:** Commit `feat: schedule lessons from effective faculty timetables`.

## Task 6: Holiday reconciliation and test dates

**Files:** Create `scheduling/reconcile.py`, `scheduling/tests_calendar.py`, `templates/scheduling/conflicts.html`, `tests/integration/test_reconciliation.py`, `tests/integration/test_test_dates.py`. Extend scheduling models/views/URLs and migrations.

**Interfaces:** Produce `ScheduleConflict(register, session, cause, proposed_change, resolved_at, revision)` and `TestEvent(register, number, session, revision)`, unique by register/test number. Produce `set_test_date(actor, register_id: UUID, *, number: int, date: date, period: str, end_period: str | None, replaces_session_ids: list[UUID], expected_revision: int, request_id: UUID) -> dict`; `change_holiday(actor, register_ids: list[UUID], *, values: dict, expected_revisions: dict, request_id: UUID) -> dict`; and `resolve_conflict(actor, conflict_id: UUID, *, action: str, reason: str, corrected_date: date | None, corrected_period: str | None, expected_revision: int, request_id: UUID) -> dict`. An empty replacement list means an extra test session. A test spanning periods reserves the full interval but creates only one attendance session; explicitly selected replaced topics return to the outstanding queue. Actions are `keep_actual`, `cancel`, `correct_actual`.

- [ ] **Step 1:** Write tests that a retroactive holiday preserves the recorded session and raises a conflict; `keep_actual` records an exception; cancellation excludes the session without deleting its prior data; and correction preserves the permanent session ID. Assert a replacement gets a new ID. Seed a future fixed test on a newly declared holiday and assert its date does not move automatically.
- [ ] **Step 2:** Write test-date assertions that Test 1 replacing a scheduled lesson leaves exactly one active session in that period, the lesson topic returns to the outstanding queue, a multi-period test counts as one event, and a second call with the same operation ID cannot create a second test.
- [ ] **Step 3:** Run `python -m pytest tests/integration/test_reconciliation.py tests/integration/test_test_dates.py -q`; expect missing conflict handling.
- [ ] **Step 4:** Implement the interfaces and conflict resolution screen. A multi-register timetable change or admin holiday must produce conflict records in every affected register. Removing a holiday may clear its unresolved conflicts but must not undo a faculty's previously accepted actual-event correction. Revalidate corrected dates against the complete faculty timetable.
- [ ] **Step 5:** Add three test-date/period controls and explicit replace-versus-extra selection. A recorded test date correction uses the same conflict workflow; cancellation never changes score weights. Expose revision and provisional state for later calculation services.
- [ ] **Step 6:** Run both test files and all scheduling tests. Require rollback of the whole multi-register change if an expected revision is stale.
- [ ] **Step 7:** Commit `feat: reconcile holidays and count internal tests correctly`.

## Task 7: Attendance persistence and cumulative calculations

**Files:** Create `attendance/models.py`, `attendance/services.py`, `attendance/calculations.py`, `attendance/views.py`, `attendance/urls.py`, `tests/unit/test_attendance_math.py`, `tests/integration/test_attendance.py` and migrations. Modify scheduling reconciliation only to trigger register revision changes and preserve attendance links.

**Interfaces:** Define `AttendanceEntry(enrollment, session, status, revision)`, unique by enrolment/session; status is `unmarked`, `present`, `absent` or `not_applicable`. Produce `save_absences(actor, register_id: UUID, *, cells: list[dict], expected_revision: int, request_id: UUID) -> dict`, `complete_session(actor, session_id: UUID, *, expected_revision: int, request_id: UUID, today: date) -> dict`, and `attendance_summary(register_id: UUID, enrollment_id: UUID, *, through: date) -> dict`. A cell contains `enrollment_id`, `session_id` and `status`. A summary returns `attended`, `eligible`, `percentage`, `sequence` keyed by session ID, and `provisional`; zero denominator yields `percentage=None`. Produce `column_totals(register_id: UUID, session_id: UUID, enrollment_ids: list[UUID]) -> dict` with `present`, `absent` and `unmarked` counts.

- [ ] **Step 1:** Write a pure calculation test for the exact register convention:

```python
result = summarise_statuses(['present', 'present', 'absent', 'present', 'absent'])
assert result['sequence'] == ['1', '2', 'A', '3', 'A']
assert result['attended'] == 3
assert result['eligible'] == 5
assert result['percentage'] == Decimal('60')
```

Define `summarise_statuses(statuses: list[str]) -> dict` in `attendance/calculations.py`; it is also used by the database-backed summary after filtering and ordering sessions. Add tests for no sessions, a late enrolment, cancelled sessions, incomplete historical attendance and block-only footers.
- [ ] **Step 2:** Write integration tests for separate same-day periods, explicit presence after completion, future-completion rejection, test-date inclusion, and later-date exclusion. With four ordinary sessions and one test, a student present at three ordinary sessions and the test must have `4/5 = 80%`. A replacement class starts without any attendance entries.
- [ ] **Step 3:** Run `python -m pytest tests/unit/test_attendance_math.py tests/integration/test_attendance.py -q`; expect missing attendance services.
- [ ] **Step 4:** Implement the services, enrolling-date checks and completion transaction. Completing a session writes explicit present entries for eligible unselected students and not-applicable entries outside enrolment dates. Treat an existing explicit absence as absent; never overwrite it because a screen omitted the cell. Reject cells belonging to a different register. Correcting a completed session writes a new audit event and revision.
- [ ] **Step 5:** Implement attendance summaries using actual dates for conducted sessions, sorted by period time and then a deterministic ID tie-breaker. Include every conducted applicable session through the end of the cutoff date. Print running numbers across leaves using session IDs. An unresolved conflict or missing applicable record makes the summary provisional; no-session percentages display a dash.
- [ ] **Step 6:** Run both attendance test files plus reconciliation tests. Verify a past-date correction changes affected later running numbers and test percentages without altering unrelated students' attendance facts.
- [ ] **Step 7:** Commit `feat: record attendance and calculate running totals`.

## Task 8: Attendance grid and reliable browser editing

**Files:** Create `static/js/api.js`, `static/js/autosave.js`, `static/js/attendance.js`, `templates/attendance/grid.html`, `tests/browser/test_attendance_workflow.py`, `tests/browser/test_save_recovery.py`. Modify existing editors, attendance views and `static/css/app.css`.

**Interfaces:** In `static/js/api.js`, export `mutate(url, {revision, requestId, values}) -> Promise<MutationResult>` using the server envelope. In `autosave.js`, export `createAutosave({readValues, write, renderStatus, debounceMs: 600}) -> {flush, dispose}`. A queued edit retains the same request ID when retrying; a later edit receives a new ID after its preceding response is reconciled. In `attendance.js`, export `selectCells({enrollmentIds, sessionIds, status})` for UI selection; the server remains authoritative.

- [ ] **Step 1:** Define browser checks for a grid with sticky USN/name columns, two periods on a date, a test, and at least 21 students. Select several absent dates for one student, complete the relevant sessions, reload, and assert selections and running totals persist. Verify whole-day selection highlights both periods while an individual-period selection affects only one.
- [ ] **Step 2:** Define recovery checks that delay a response, drop a response after server commit, reject an edit with HTTP 409, and interrupt the network. Assert that the UI displays Saved only after an acknowledged revision, a retry is not duplicated, a later keystroke cannot be replaced by an older response, and conflicting values are shown for review. Test keyboard selection and accessible status announcements.
- [ ] **Step 3:** Run `python -m pytest tests/browser/test_attendance_workflow.py tests/browser/test_save_recovery.py --browser chromium -q` against pytest-django's disposable live server; expect missing grid or save-state behaviour. Use Playwright route interception for delayed, dropped and conflicting responses while retaining real service tests for server-side guarantees.
- [ ] **Step 4:** Implement shared request and autosave modules, including CSRF tokens, field errors, visible unsaved state and revision conflict handling. Apply the module to metadata, student and lesson editors; Task 9 reuses it for marks. Explicit Apply remains mandatory for pasted batches and consequential scheduling changes.
- [ ] **Step 5:** Implement the attendance grid with student rows fixed on the left, dated periods across the right, a date-range filter, bulk selection review, Complete attendance and correction controls. Show unconfirmed/future columns without assumed attendance, distinguish tests and show block and overall totals clearly. The mobile layout may scroll; it must not obscure which student is selected.
- [ ] **Step 6:** Run the same two browser test files; verify all assertions and inspect the grid at desktop and narrow widths. Capture only synthetic data in screenshots.
- [ ] **Step 7:** Commit `feat: add attendance calendar grid and resilient autosave`.

## Task 9: Configurable marking templates and marks entry

**Files:** Create `assessments/models.py`, `assessments/rules.py`, `assessments/calculations.py`, `assessments/services.py`, `assessments/views.py`, `assessments/urls.py`, `templates/assessments/rules.html`, `templates/assessments/marks.html`, `static/js/assessments.js`, `tests/unit/test_scores.py`, `tests/integration/test_marks.py` and migrations. Extend paste validation and browser editing.

**Interfaces:** Define `MarkingTemplate(owner, name, definition, revision)`, a `RegisterMarkingRule(register, definition, source_template, revision)` snapshot, and `Mark(enrollment, assessment_key, value, status, revision)`. Keys are exactly `A1`, `A2`, `A3`, `T1`, `T2`, `T3`; statuses are `missing`, `scored`, `absent`. `validate_rule(definition: dict) -> list[dict]`; `calculate_score(definition: dict, marks: dict[str, dict]) -> dict` returns `status`, `unrounded`, `rounded`, `contributions` and `pending_keys`. `apply_marking_template(actor, register_id: UUID, *, template_id: UUID, expected_revision: int, request_id: UUID) -> dict`; `save_marks(actor, register_id: UUID, *, rows: list[dict], expected_revision: int, request_id: UUID) -> dict`.

Rule JSON schema version 1 contains `final_maximum`, `rounding`, `assessments` mapping each key to a maximum, and `components`. Each component contains `id`, `kind` (`individual` or `group`), `assessment_keys`, `weight_percent`, `aggregation` (`individual`, `mean_normalised`, `sum_ratio`, `best_n`) and optional `best_n`. Independent components have one key. A key cannot occur in two enabled components. Rounding choices are `whole_half_up`, `one_decimal_half_up`, `two_decimals_half_up`, `whole_ceiling`, `whole_floor`.

- [ ] **Step 1:** Write tests for a 60-percent test group and 40-percent assignment group on a final maximum of 50. Normalised group scores 0.8 and 0.9 must give `Decimal('42')`. With scores 10/20 and 15/50, `mean_normalised` gives 0.4, `sum_ratio` gives 25/70, and best-one gives 0.5. Verify best-two ordering uses normalised values rather than raw marks.
- [ ] **Step 2:** Add tests for weights totalling 99.99 or 100.01, zero/negative maxima, duplicate membership, invalid best-N, AB versus missing, exact half-up rounding, and a missing candidate in best-N. A missing zero-weight assessment must not block completion. Assert that blank pasted cells preserve saved marks, explicit clear makes them missing, and reordered USNs preserve student associations.
- [ ] **Step 3:** Run `python -m pytest tests/unit/test_scores.py tests/integration/test_marks.py -q`; expect missing rule and score services.
- [ ] **Step 4:** Implement schema validation and calculations using Decimal values from strings. Keep intermediate precision, round once at the final result, and return pending when required candidates are missing. Do not execute arbitrary expressions. Model validation and service validation must both reject marks outside their maxima.
- [ ] **Step 5:** Implement marking-template save/reuse with snapshot semantics and a before/after preview when applying changes to an existing register. Add the percentage/maxima/rule editor and a worked calculation preview. Add USN-based pasted and direct mark entry with visible AB, zero and missing states. Highlight disagreement with test attendance without changing either record.
- [ ] **Step 6:** Run score, marks and roster import tests. Add a browser check in the existing workflow runner that editing a template does not silently change a previously configured register and that reducing a maximum below a saved mark requires correction before applying.
- [ ] **Step 7:** Commit `feat: configure assessment weights and calculate marks`.

## Task 10: Integrated Word exports and consistent snapshots

**Files:** Create `exports/snapshot.py`, `exports/models.py`, `exports/views.py`, `exports/urls.py`, `templates/exports/preview.html`, `tests/integration/test_export_snapshot.py`, `tests/integration/test_docx_export.py` and migrations. Modify the Task 3 renderer and guide.

**Interfaces:** `build_export_snapshot(actor, register_id: UUID, *, through: date, draft: bool) -> dict`; `create_export(actor, register_id: UUID, *, through: date, draft: bool, expected_revision: int, request_id: UUID) -> ExportRecord`; `download_export(actor, export_id: UUID) -> FileResponse`. `ExportRecord` stores ownership, register revision, schema version, snapshot, generated-file checksum, creation time and protected file location. Consume `render_booklet(snapshot, target)`, Task 7 attendance functions and Task 9 scoring.

Snapshot schema version 1 contains `register`, `export_date`, `source_revision`, `students`, `lessons`, `sessions`, `attendance`, `column_totals`, `assessments`, `timetable`, `warnings` and `draft`. Students include stable IDs, USN, name and serial order. Sessions include stable IDs, consecutive display numbers, date, period, kind and status. Attendance maps student and session IDs to display cells plus cumulative/test summaries. Assessments include raw marks, pending state, contributions, configured maxima and final results. This is the contract implemented by the synthetic fixture in Task 3.

- [ ] **Step 1:** Write snapshot tests that capture one consistent revision while another request edits a mark, deny foreign export downloads, and verify re-downloading an issued export returns the same bytes after subsequent edits. Assert that future test marks remain blank through an earlier cutoff, current assignment marks remain included, and an overall score needing that future test is pending.
- [ ] **Step 2:** Write document tests for 0, 1, 20, 21 and 61 students and 0, 75 and 76 sessions, inspecting XML for every USN, date, assessment maximum and section size. Confirm cancelled sessions are omitted, session numbers are consecutive, and a presence following the 75th session continues the same student's count. Confirm future/unconfirmed attendance stays blank and signature areas contain no copied handwriting.
- [ ] **Step 3:** Run `python -m pytest tests/integration/test_export_snapshot.py tests/integration/test_docx_export.py -q`; expect missing snapshot integration.
- [ ] **Step 4:** Implement a short transaction that captures the current consistent data and calculation inputs, then compute/render from that immutable capture outside the write transaction. Save the output atomically with its snapshot and checksum. Check the revision again when committing the export receipt; if a change occurred, present the export as tied to the captured revision rather than relabelling it as the latest data.
- [ ] **Step 5:** Wire the renderer to actual metadata, lesson plans, running counts, block footers, all three test percentages, weighted labels and timetable effective date. Include original planned and actual dates; add revised-date notes without erasing faculty remarks. Preserve blank capacity and repeat continuation blocks above the base capacity. Add draft markings outside the table body without displacing alignment.
- [ ] **Step 6:** Add preflight and preview showing unresolved conflicts, invalid rules, incomplete conducted sessions and fit warnings. Block a final export for conflicts or invalid data; leave genuinely pending marks blank with visible explanation. Long content must be fully rendered or explicitly flagged for correction before final output. Include the separate assembly guide and calibration sample.
- [ ] **Step 7:** Run export and geometry tests, render every page of a typical and an overflow example, and inspect the PDF or page images. Recheck physical Word/printer assembly when available; record which checks were actually performed and which remain pending.
- [ ] **Step 8:** Commit `feat: export saved registers in the original booklet layout`.

## Task 11: Backups and safe restoration

**Files:** Create `operations/backups.py`, `operations/views.py`, `operations/urls.py`, `templates/operations/backups.html`, `operations/management/commands/backup_registers.py`, `operations/management/commands/restore_registers.py`, `tests/integration/test_backups.py`, `tests/integration/test_restore.py`. Add persistent backup-operation records and migrations in `core/models.py` as required.

**Interfaces:** `create_backup(*, data_dir: Path, destination: Path, now: datetime) -> Path`; `validate_backup(path: Path) -> dict`; `restore_backup(*, archive: Path, data_dir: Path, maintenance: bool) -> dict`; `prune_backups(directory: Path, *, keep_daily: int = 30) -> list[Path]`. Validation returns schema/application versions, integrity status and manifest checksums. Restoration is run by a separate maintenance process, not inside an active Django request using the database it replaces.

- [ ] **Step 1:** Write a round-trip test with two faculty registers, attendance, marking rules and issued exports. Restore into a disposable data directory and assert records, ownership and checksums match. Assert ordinary faculty cannot create, list, download or restore whole-system backups.
- [ ] **Step 2:** Add failure tests for corrupt ZIP data, archive path traversal, unsupported schema version, incomplete output, a simulated disk-full write and a held Windows-style file lock. In every case assert the current working database is intact and a failed backup never appears as successful. Confirm only successful daily backups are pruned and 30 daily copies remain.
- [ ] **Step 3:** Run `python -m pytest tests/integration/test_backups.py tests/integration/test_restore.py -q`; expect missing operations.
- [ ] **Step 4:** Implement online database backup through SQLite's backup API, manifest checksums and temporary-file-to-final-name replacement. Include referenced immutable export files and the configuration manifest. Keep the local certificate authority's private keys in a separate protected host backup, never in a faculty-accessible download. Take a consistent export-file manifest from the backed-up database, not a later live query.
- [ ] **Step 5:** Implement restoration through maintenance mode: reject new writes, stop the application process, validate the archive, create a verified recovery backup, close database handles, restore atomically, invalidate sessions and restart. On a failure keep the pre-restore database selected. Expose admin status and actionable errors; never restore a supplied archive path without path validation.
- [ ] **Step 6:** Run both test files and exercise the management commands against disposable data. Verify a backup taken while another register is being saved corresponds to a valid database revision and can be restored.
- [ ] **Step 7:** Commit `feat: back up and restore faculty registers safely`.

## Task 12: Windows packaging and complete workflow verification

**Files:** Create `operations/runtime.py`, `scripts/windows/setup.ps1`, `scripts/windows/start.ps1`, `scripts/windows/stop.ps1`, `scripts/windows/install-startup.ps1`, `scripts/windows/Caddyfile.template`, `scripts/windows/check-install.ps1`, `tests/integration/test_runtime.py`, `tests/browser/test_full_workflow.py`, `docs/windows-setup.md`, `docs/verification.md`. Modify `README.md`, configuration and account/admin links as needed.

**Interfaces:** `operations.runtime.main(argv: list[str] | None = None) -> int` starts and supervises the local application and scheduled backup checks; `runtime_config(data_dir: Path) -> dict` validates directories, addresses, ports and TLS paths. Keep Waitress on `127.0.0.1:8000` by default, Caddy on LAN HTTPS port 8443, and make both configurable with validation. The browser address is printed by the launcher. Store data by default under the host operator's local application-data folder, with a documented alternate persistent path.

- [ ] **Step 1:** Write runtime tests that an invalid data directory fails before startup, a second process cannot acquire the host lock, a missed daily backup runs on the next start, and changing program versions does not replace the database. Assert runtime state and local signing keys are excluded from logs and distribution archives.
- [ ] **Step 2:** Run `python -m pytest tests/integration/test_runtime.py -q`; expect missing runtime lifecycle behaviour.
- [ ] **Step 3:** Implement supervised start/stop, an exclusive process lock and daily backup scheduling with Task 11. No backup scheduler should be started once per web worker. Setup resolves and validates the supported interpreter, installs locked dependencies, backs up before migrations, runs migrations, collects local static files and invokes the administrator bootstrap. Do not enable startup until setup checks pass.
- [ ] **Step 4:** Implement Windows scripts and Caddy configuration with loopback-only trusted forwarding, secure session cookies and the configured allowed hostname. Serve `/static/` from the collected local asset directory and forward application paths to Waitress. Support the institution certificate or a locally generated CA and give exact client root-install instructions. Show the required private-network firewall rule and let setup apply it when explicitly selected; never enable public network exposure or change unrelated firewall rules. Obtain Caddy from its official release source with an explicit version and checksum recorded in the package manifest.
- [ ] **Step 5:** Write and run the full synthetic browser workflow: create two accounts, paste 21 students and lessons, enter timetable versions, complete classes, record absences, add a retroactive holiday, resolve it, set/complete a test, paste reordered marks, configure 60/40 weighting, export and reopen the DOCX, and restore a backup in a disposable installation. Assert private ownership, saved reload state and matching screen/export totals at each relevant checkpoint.
- [ ] **Step 6:** Run `python -m pytest tests/unit tests/integration -q`, `python manage.py makemigrations --check --dry-run`, `python manage.py check`, and `python manage.py check --deploy` under the production HTTPS configuration. Run the documented browser suite. Require no failed tests, no uncommitted model migrations and no unresolved deployment-check findings; record actual command output in the verification note without secrets.
- [ ] **Step 7:** On a Windows host run `powershell -ExecutionPolicy Bypass -File scripts/windows/check-install.ps1`, including launch, a second-PC HTTPS login, restart persistence, backup and restore. Open the sample in Word, print at actual size, measure 210/105 by 307 mm and assemble it between the existing covers. If the current environment cannot run these checks, deliver the completed scripts and samples and list those exact checks as pending; never call simulated checks Windows verification.
- [ ] **Step 8:** Finish `docs/windows-setup.md`, `docs/print-guide.md` and the concise faculty workflow guide in `README.md`. Include start/stop, account creation, pasted-table examples, historical corrections, mark rules, backup/restore and correct printing. Package source, locks, scripts and guides, excluding real data, photographs, credentials and generated private artifacts.
- [ ] **Step 9:** Commit `feat: package Windows deployment and verify register workflow`. Have another student review the complete application against the acceptance table, fix actionable defects and rerun the affected checks plus the final suite. Demonstrate the application and a printed booklet to the faculty supervisor before deployment on the shared college PC.

## Coverage map and handoff

| Approved specification section | Owning tasks |
| --- | --- |
| Agreed scope and physical references | 3, 10, 12 |
| Faculty workflow and screens | 1, 2, 4, 5, 8, 9, 10 |
| Accounts, ownership and saved work | 1, 2, 8, 11 |
| Structured data entry | 4, 5, 9 |
| Schedule and lesson execution | 5, 6 |
| Retrospective corrections | 6, 7, 10 |
| Attendance rules and block totals | 7, 8, 10 |
| Test dates and cumulative cutoffs | 6, 7, 10 |
| Configurable assessment rules | 9, 10 |
| Word export and booklet assembly | 3, 10, 12 |
| Module architecture and revision consistency | 1, 2 and the interfaces of all subsequent tasks |
| Windows operation and recovery | 11, 12 |
| Acceptance scenarios | Relevant test steps in Tasks 1 to 12 and the complete workflow in Task 12 |

Keep runtime dependencies and render/browser tools scoped to the approved implementation. The first release remains the six-heading theory register. Additional laboratory layouts or external integrations are outside this plan.

The student team owns implementation. Assign an owner and reviewer for each task, keep the service contracts consistent, and demonstrate each milestone to the faculty supervisor. The four milestones are: accounts and print sample after Task 3; reliable input and scheduling after Task 6; attendance and assessment workflow after Task 9; and complete export, recovery and Windows deployment after Task 12. A milestone is complete only when its stated checks pass; physical print verification remains a separate recorded acceptance check.

## Technical sources checked for this plan

- Python 3.12 is supported by the selected Django 5.2 series; use a current compatible patch release. [Django Python compatibility](https://docs.djangoproject.com/en/5.2/faq/install/)
- SQLite does not implement `select_for_update`; short immediate transactions and conditional revisions are the selected concurrency approach. [Django SQLite notes](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes)
- Waitress supports Windows and provides the WSGI server used behind Caddy. [Waitress documentation](https://docs.pylonsproject.org/projects/waitress/en/stable/)
- DOCX section dimensions and margins can be set explicitly, but this does not itself prove printed fidelity. [python-docx sections](https://python-docx.readthedocs.io/en/latest/user/sections.html)
- Local HTTPS certificates require the CA root to be trusted on client devices. [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- Browser workflow tests use the official pytest integration and its browser fixtures. [Playwright Python test runners](https://playwright.dev/python/docs/test-runners)

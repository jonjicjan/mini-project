# Faculty attendance register application design

Approved by the user on 1 October 2026. This document specifies the application to be built. It is not a claim that the application or print template has been implemented or tested.

The agreed scope below records the user's decisions. Detailed operational rules and technical choices in later sections are the implementation defaults accepted with this specification.

The application will replace manual preparation of the supplied attendance booklet. Faculty will paste or enter their lesson plans, students, timetables and marks, record absences, and generate an editable Word document containing replacement interior sheets. One Windows PC will host the application and its saved data. Faculty will access it through browsers on the college network using individual logins.

## Agreed scope

The following requirements were established with the user:

- Reproduce the existing booklet, including its half-width attendance leaves. Full pages measure 210 mm wide by 307 mm high; half-pages measure 105 mm wide by 307 mm high.
- Omit cover pages. Print the interior sheets and place them between the existing physical covers. Include the faculty timetable as a printable insert.
- Populate the first three lesson-plan pages, attendance headers and student rows from entered data. Preserve the supplied headings, grid structure and signature spaces.
- Use structured copy and paste and direct editing instead of document uploads or document extraction.
- Show students on the left and dates and periods across the right in the attendance screen. Support selecting several absences for each student.
- Print a cumulative attended-class count for presence and a red A for absence, with class totals and attendance percentages.
- Allow faculty to specify when a revised timetable becomes effective and to enter unplanned holidays at any time.
- Keep saved attendance intact when resolving retrospective changes. Recalculate all affected results after corrections.
- Support three assignments and three tests in the supplied layout. Let faculty configure their contribution to the final mark, including percentages and aggregation rules.
- Record the three test dates. Each test is one attendance session, and each test attendance percentage is cumulative from the start through that test date, including the test session.
- Provide individual accounts, central saving, administrator account management, and database backup and restore.

## Reference material and print interpretation

The 24 photographs in the project folder are layout references. The numbered filenames are in the user's stated page order. Several photographs show overlapping or folded leaves, so a photograph must not automatically be treated as one physical printed side.

| Reference | Use |
| --- | --- |
| `page2.JPG`, `IMG_1640.JPG`, `IMG_1641.JPG` | Three lesson-plan pages, including metadata, topic rows, planned and execution dates, remarks and signatures |
| `IMG_1642.JPG` through `IMG_1647.JPG` | First attendance block, student serial numbers 1 to 20, class columns and assessment panel |
| `IMG_1648.JPG` through `IMG_1653.JPG` | Second attendance block, student serial numbers 21 to 40 |
| `IMG_1654.JPG` through `IMG_1659.JPG` | Third attendance block, student serial numbers 41 onward, with unused rows through 60 |
| `inside cover page.JPG` | Rules for running attendance counts, red absence marks and attendance on test dates; this cover page is not exported |
| `inside of back cover.JPG` | Timetable layout, effective date, faculty and course details, and signatures; export this content as an interior insert |
| `cover page.JPG` | Course and institution metadata reference only; do not export the cover |

The attendance format accommodates 20 student rows per block and 75 numbered session columns. Continue cumulative attendance across leaves; never restart counts at a page boundary. The print template must maintain row alignment between the roster, continuation leaves and marks panel.

The first lesson-plan page has rows for classes 1 to 20, the second for 21 to 45, and the third has the remaining rows and closing signatures. The template will reproduce the printed row capacity, including empty rows, rather than the accidental amount of handwriting in the example.

The leaf sequence must be reconstructed from the folded and unfolded references. Its acceptance check is that the roster and continuation columns can be read together after assembly, without duplicated or omitted session columns. Physical side order and binding alignment will be verified with a sample print; the source images alone do not verify duplex feed direction or printer margins.

## Faculty workflow

1. Log in and open or create a register identified by academic year, semester, branch, section, subject code and subject name. Store the faculty name and term start and end dates.
2. Paste the student list and lesson plan into labelled tables. Review and correct the preview, then import it.
3. Enter the faculty's weekly timetable, including period times, breaks and other subjects, with an effective-from date. Associate the relevant subject and section with this register.
4. Review the generated session calendar and any mismatches between lesson-plan dates and timetable slots. Add holidays, tests and exceptional classes as needed.
5. Record attendance using the student grid. Confirm conducted sessions and mark absences. Reopen a previous session to correct an entry.
6. Configure or reuse the assessment template and paste marks matched by USN.
7. Review calculations and resolve outstanding conflicts. Choose an export date and generate the interior booklet as DOCX.

The main screens are My Registers, Register Setup, Students, Lesson Plan, Timetable and Calendar, Attendance, Assessments, and Print Preview. The administrator has a separate account and backup management screen. Use readable tables, sticky student columns and headers, keyboard navigation, and horizontal scrolling for long attendance grids.

## Accounts and saved work

Faculty accounts can access only their own registers, student lists, schedules, marking templates and exports. Enforce ownership on the server for every read, write and download, not just by hiding links. Administrators can manage accounts and restore the institution's saved data; administrative access is privileged and is not described as private from the administrator.

The administrator creates faculty accounts, disables accounts and resets passwords. There is no public registration or email dependency. Password resets invalidate existing sessions. Disabling an account preserves its registers.

Valid small edits save automatically after a short pause and on leaving a field. Display Saving, Saved, or Not saved with a useful retry message. A failed request must never be displayed as saved. Pasted batches and changes with consequences have a preview and explicit Apply action.

Every mutable record carries a revision. A stale browser cannot overwrite newer changes silently: the server returns a conflict and the screen offers the current and attempted values. Save a batch atomically or reject it with row-specific errors. Retrying a successful operation must not create duplicate sessions or marks.

Keep an audit history for attendance corrections, schedule changes, marking-rule changes and administrative actions, recording the actor, time, reason where required, and changed values. Archive registers rather than removing their historical records.

## Structured data entry

Accept plain tab-separated rows copied from spreadsheets or Word tables. Also accept comma-separated text through an explicit paste-format choice. Provide labelled example rows and column mapping when the pasted column order differs. Do not infer tables from narrative prose or scanned images.

| Table | Fields |
| --- | --- |
| Students | USN, full name, optional serial number and enrolment dates |
| Lesson plan | Original class number, topic, planned date, optional planned period, optional execution date and remarks |
| Timetable | Weekday, period number, start and end time, subject code, section and activity; effective date belongs to the timetable version |
| Marks | USN and values for A1, A2, A3, Test 1, Test 2 and Test 3; a batch may contain only some assessment columns |

Dates use the explicitly displayed day-month-year convention. Accept `DD/MM/YYYY`, `DD-MM-YYYY` and ISO dates; reject two-digit years and impossible dates. Store dates as calendar dates in Asia/Kolkata. Store audit timestamps separately in UTC.

Trim accidental surrounding whitespace, preserve names as text, and match marks by USN rather than row position. USN matching is case-insensitive with a consistent uppercase display; preserve meaningful characters and leading zeros. Reject duplicate USNs within a register. Flag unknown USNs in marks instead of creating students implicitly.

A repeated student import offers add or update by USN; it never replaces the roster wholesale. Preserve the original serial order unless the faculty explicitly reorders it. Changing a student's USN requires a deliberate correction on the existing student record so attendance remains attached. Adding a student after sessions have been recorded requires an enrolment start date and review of applicable historical attendance; do not invent past presence.

Blank marks are missing, numeric zero is a score of zero, and AB is an explicitly absent assessment with zero scoring credit. Blank cells in a pasted update leave existing marks unchanged; clearing an existing mark is an explicit action. Marks must be within the configured maximum. A test attendance absence and an AB mark are separate facts; highlight disagreement but do not overwrite either automatically.

## Schedule and lesson execution

Separate four concepts: the original lesson plan, effective timetable versions, actual class sessions, and attendance for those sessions. Each session has a permanent identifier independent of its displayed number, date or topic.

A faculty timetable version contains the complete weekly timetable and an effective-from date. It applies until the next version starts. The latest version whose start date is on or before a session date supplies that day's timetable. Reject two versions with the same effective date unless the user is explicitly editing that version. Keep earlier versions for historical reconciliation and timetable printing.

Timetable versions belong to the faculty and academic term, and can be shared by that faculty's registers for the term. Editing a version updates each linked register and reports the affected registers. Check the complete timetable for overlapping teaching assignments, not only the currently open subject.

Build available teaching slots from the matching subject and section within the term, excluding active holidays and cancellations. Sessions may share a date but must be distinguishable by period. Test and lesson sessions for the same register cannot occupy the same period unless the test explicitly replaces that lesson session.

Preserve entered original planned dates. If an entered date does not match an available slot, highlight the mismatch and propose the next available slot. Faculty can accept rescheduling or mark an exceptional class with a reason. Store the revised scheduled date separately from the original planned date and the actual execution date.

When a future timetable or holiday changes, keep completed sessions fixed and place outstanding topics, in their original order, into the earliest available slots from the affected date. Respect explicitly fixed test dates and exceptional classes. Do not extend past the term end silently: list unplaced topics as needing extra classes or a revised term end. Repeating this calculation without new input must produce the same schedule.

For a retrospective change, do not fabricate new classes in elapsed slots. Keep past unconfirmed sessions visible for reconciliation or attendance back-entry; automatically allocate future outstanding topics only from the later of today and the effective date. Pasting an execution date records a claimed conducted session with attendance still unmarked; it never supplies student presence automatically.

Faculty can add a one-day holiday or a date range, edit it, or remove it at any time. Holiday exclusions are attached to the relevant register by default. An administrator can apply a college holiday to selected registers in one operation, with the same reconciliation behaviour in each affected register. A confirmed exceptional class can override a holiday with a recorded reason.

### Retrospective corrections

For each recorded session affected by a timetable change, holiday, cancellation or date correction, offer the following explicit outcomes:

- Keep it as a class that actually occurred, with an exception reason.
- Cancel the session and exclude it from all counts, while retaining the previous attendance in history.
- Correct the actual date or period of the same conducted session, preserving its attendance after the faculty confirms that it represents the same event.

A replacement class is a new session with unmarked attendance; it does not inherit the old session's absent students. Editing a holiday must never shift an absence onto a different class by matching a date or column position.

An unresolved historical conflict leaves the existing recorded fact in place and marks results as provisional. Once resolved, recalculate running counts, present and absent totals, test percentages, final percentages, scheduled topics and print headers in one consistent revision. A final export cannot contain unresolved schedule conflicts.

## Attendance rules

Sessions have planned, conducted or cancelled status. Attendance has unmarked, present, absent or not-applicable status. Enrolment start and end dates determine whether a student is applicable to a session; default enrolment covers the whole term. Not-applicable attendance is outside both the numerator and denominator.

Future sessions are visible but cannot have attendance completed before their date. The Complete attendance action confirms that the session occurred and records all applicable unselected students as present. These are saved as explicit present records, not inferred forever from the absence of an absence record. Changes to the date of a session with draft absence selections require review of those selections before completion.

The grid supports selecting individual cells, multiple dates for one student, and a whole day's applicable sessions. When a date contains multiple periods, day selection visibly selects all of them; individual periods can still be changed. Test sessions are labelled distinctly. Bulk edits have undo or a reviewable correction path.

For each student, traverse confirmed, applicable sessions in actual date and period order:

- Present increments the running attended count and prints the new number.
- Absent prints a red A and leaves the count unchanged.
- Future, cancelled and unmarked entries never increment the count. Not-applicable entries print a dash.

For example, P, P, A, P, A prints 1, 2, A, 3, A. The example has three attendances out of five confirmed sessions, or 60 percent. Continue the count across all leaves and student blocks for that student.

Daily column footers show the number present and absent among the displayed block's applicable students. A register-wide summary may also be shown on screen, clearly distinguished from a block's printed totals. Blank student rows do not contribute.

The percentage is 100 multiplied by attended sessions divided by applicable conducted sessions. A zero denominator displays a dash, never zero or 100 percent. If historical attendance is incomplete, show that the result is provisional rather than silently treating missing entries as present or absent.

## Test dates and attendance cutoffs

Store dates and period identifiers for Tests 1, 2 and 3. Entering a test creates one planned attendance session for that test. A test may replace a scheduled teaching period or be an extra session; make that choice explicit. When replacing a teaching period, defer its outstanding topic and count the period only once. A test occupying several clock periods still counts as one attendance session under the agreed rule.

For a test on date D, include every applicable conducted session from the student's eligible start through the end of D, including the test itself. This is a date-inclusive cutoff, not a cutoff at the test's starting time. For tests on the same date, the attendance cutoff is therefore the same.

Until a test has been conducted and its attendance completed, its percentage is provisional on screen and blank in a final export. After completion, unrecorded earlier sessions must be resolved before that test percentage can be exported as final. Subsequent same-day or backdated corrections recalculate it automatically.

Moving a test that already has attendance requires the same historical reconciliation as other sessions. Cancelling a test removes its attendance session from the denominator but does not silently redistribute its mark contribution; faculty must correct the assessment rule separately. The final attendance percentage uses all applicable conducted sessions through the chosen export date.

A holiday or revised timetable that conflicts with a fixed future test raises a scheduling conflict. Keep the test's date unchanged until the faculty reschedules it, cancels it or records an explicit exception. Ordinary topic rescheduling must not move a test date silently.

## Configurable assessment rules

Each register has a snapshot of a reusable faculty-owned assessment template. Editing the reusable template does not silently change existing registers. Applying a revised template to a register shows the changed rules and recalculates that register after validation.

The supplied booklet has A1, A2, A3 and Tests 1, 2 and 3. These are the six available scoring headings in the first release. Each has an editable maximum mark and may have an individual percentage contribution. Alternatively, assignments and tests can each form a group with its own percentage contribution and aggregation rule. An assessment cannot contribute both independently and inside a group.

Supported group rules are an average of normalised scores, a sum of earned marks divided by the sum of maximum marks, and the average of the best N normalised scores. Best N must be between one and the number of included assessments. These options provide flexible rules without executing faculty-entered program code.

For an individual assessment, its normalised score is earned marks divided by maximum marks. A group's rule produces a normalised score between zero and one. The final mark is:

`final maximum × sum(normalised component score × component percentage / 100)`

The enabled contributions must total exactly 100 percent using decimal arithmetic. Each enabled maximum must be positive. Zero-weight assessments can remain visible for record keeping but do not block a final score. Missing required marks keep the result pending; never rescale remaining weights to hide a missing assessment. Best-N results remain pending until every candidate assessment has a mark or an explicit AB entry.

Faculty chooses the final maximum and final rounding: nearest whole mark, nearest one or two decimal places, round up to a whole mark, or round down to a whole mark. Use half-up for nearest rounding. Carry full decimal precision through intermediate calculations and round the final result once. Show the unrounded calculation in the preview.

Example: tests contribute 60 percent, assignments 40 percent, and the final maximum is 50. A test-group score of 0.8 and an assignment-group score of 0.9 produce `50 × (0.8 × 0.6 + 0.9 × 0.4) = 42`.

Print individual raw assessment marks with their configured maxima. The assignment summary and final test-summary cells show their contributions on the final scale, and the overall cell shows their sum after final rounding. Preserve the existing assessment panel's column structure; adjust maximum-mark labels and use Score instead of Avg when the selected rule is not an average. A changed score maximum or weighted rule must never leave misleading printed labels.

## Word export and booklet assembly

Generate editable DOCX tables and text, not photographs of blank forms with text placed over them. Recreate institutional headings and branding from the references; leave signature and initials spaces blank. Do not reproduce handwritten signatures or prepopulate real student records from the reference photographs.

Export the lesson-plan section, repeated attendance and assessment blocks, then the timetable insert. No front cover, vision and mission cover page, or outer back cover is included. The latest timetable version effective on the selected export date is printed with its effective-from date. Earlier versions remain available as optional additional timetable inserts.

Attendance headers contain session number, period and date. Planned lesson information initially supplies the schedule, but confirmed actual dates and periods control the executed attendance columns. Keep lesson-plan class numbers separate from attendance-session numbers because tests also count as sessions.

Number attendance columns consecutively across active sessions, ordered by actual date and period for conducted sessions and scheduled date and period for planned sessions. Cancelled sessions are omitted from the active columns but retained in history and relevant lesson remarks. Renumbering a column must not change a session identifier or which attendance records belong to it.

The printed lesson plan retains its Plan and Execution columns. Plan shows the original planned date; Execution shows the confirmed actual date. When scheduling changes, add a concise revised-date note in Remarks without erasing faculty-entered remarks. The app's schedule view separately shows the current revised date.

Use fixed table geometry, explicit page breaks and section sizes of 210 by 307 mm or 105 by 307 mm as appropriate. Prevent student rows from splitting across pages. Keep empty roster rows and unused class cells as in the blank booklet. Long names and topics must wrap within their cells or trigger a visible fit warning, never silently disappear or overlap other fields.

Registers are not restricted to 60 students or 75 total sessions. Add another 20-student block as necessary. Above 75 sessions, add a clearly numbered continuation block using the same leaf pattern, continuing both session numbering and running attendance. Preserve the base three lesson-plan pages and use an additional continuation page if their row capacity is exceeded. Do not squeeze additional columns into the original geometry.

Normal export includes all planned columns up to the term's scheduled end, leaving attendance after the selected export date blank. Use that date as the attendance cutoff and leave later tests' marks and percentages blank even if someone has entered marks early. Assignment marks use the current saved values because assignment dates are not an input in this release. A total requiring a test beyond the cutoff stays blank. This is a current corrected report with an attendance cutoff, not a reconstruction of what was known at a past time. Retain an immutable export snapshot and its generated document when an exact previously issued version is needed.

A draft export may contain clearly marked unresolved or incomplete results. A final export blocks on schedule conflicts, invalid marking rules, unknown required student mappings, and incomplete attendance for sessions declared conducted. Unentered future assessment marks can stay blank; incomplete required past marks leave their totals blank with an actionable warning. Never print a fabricated total.

Provide a separate print and assembly guide listing leaf order, dimensions and blank sides where needed. Include an optional calibration sheet outside the register showing measured dimensions and row alignment marks. Printing must use actual size. The target 307 mm page height is greater than standard A4; the Windows printer must use suitable custom or larger stock trimmed to size. Half-width leaves may be printed on suitable stock and trimmed using the guide. Do not silently scale the booklet to fit A4.

Visual comparison against the photos and a physical test print in Word on the target Windows printer are required before declaring the template an exact replacement. Formatting measurements derived from photographs are initial reconstruction values; the user-confirmed physical page sizes are authoritative.

## Application architecture

Use a single Python application built with Django, served on Windows by Waitress, with SQLite on the host PC and DOCX generation through python-docx. Use server-rendered pages with focused browser JavaScript for paste previews, attendance selection and autosaving. Bundle browser assets locally so routine use does not depend on public CDNs or internet services.

This choice follows the approved single-host architecture. Django supplies an account and session foundation; ownership checks and the register rules still require explicit application code. [Django authentication documentation](https://docs.djangoproject.com/en/5.2/topics/auth/default/)

SQLite is selected because only the application server will open the database on its own local disk. Faculty browsers will communicate with the server, never open a shared database file. Keep transactions short and handle busy writes with bounded retries. [SQLite deployment guidance](https://www.sqlite.org/whentouse.html)

Waitress provides the Windows-compatible application-serving component. The production deployment must use its supported configuration rather than a development server. Dependency versions will be pinned and checked for compatibility during implementation. [Waitress documentation](https://docs.pylonsproject.org/projects/waitress/en/stable/)

python-docx supports section-level page dimensions and margins; print fidelity still requires template construction and rendering checks. [python-docx section documentation](https://python-docx.readthedocs.io/en/latest/user/sections.html)

Keep modules separate by responsibility:

| Module | Responsibility |
| --- | --- |
| Accounts | Login, sessions, faculty ownership and administrative account actions |
| Registers | Course metadata, student enrolment, original lesson plan and paste validation |
| Scheduling | Timetable versions, holidays, tests, exceptions, actual sessions and conflict resolution |
| Attendance | Per-student session records, bulk selection, completion and running totals |
| Assessment | Assessment definitions, mark entry, template validation and score calculations |
| Export | Immutable calculation snapshot, Word geometry, leaf ordering and print checks |
| Operations | Audit events, backups, restoration, migrations and Windows start-up |

Persist users, registers, student enrolments, lesson-plan rows, timetable versions and entries, holiday exclusions, sessions, attendance entries, assessment templates and snapshots, marks, audit events and export snapshots. Attendance is unique by enrolment and permanent session identifier. Marks are unique by enrolment and assessment identifier.

Compute all displayed and printed totals from the same calculation functions. A data change and its conflict state commit atomically; exports read one consistent saved revision. Cache only derived results that can be invalidated by the affected register revision. Re-importing or rebuilding a schedule must not duplicate its sessions.

## Windows operation and recovery

Deliver Windows setup instructions, a launcher that displays the local browser address, and an optional start-at-login configuration. Keep program files separate from the persistent database, backups, configuration and export files so updating the application does not erase saved work. Routine faculty use requires only a browser; the host PC and college network must be available.

Use framework password hashing, server-managed sessions, CSRF protection, bounded login attempts and server-side validation. Configure the allowed LAN hostnames and one externally accessible application port. Bundle Caddy as the HTTPS front end on the Windows host, forwarding to Waitress on loopback. Use an institution-trusted certificate when supplied, otherwise a local certificate authority whose public root is installed on faculty devices during setup. Keep the signing key on the host. Localhost HTTP can be used during setup; routine LAN logins use HTTPS. No public hosting, email or third-party account is required. [Caddy local HTTPS documentation](https://caddyserver.com/docs/automatic-https)

Record an automatic daily backup when the application is running, retain 30 daily backups by default, and allow an administrator to download a backup or choose a second backup directory. Create a backup before schema migrations and before restoration. Include configuration needed to interpret the database and stored export snapshots, but keep account secrets out of logs.

Use the database backup API rather than copying a live database file blindly. Validate the backup and its application schema version before reporting success. Restoration enters maintenance mode, preserves the current database as a recovery copy, restores the selected backup, and invalidates existing sessions. [SQLite backup documentation](https://www.sqlite.org/backup.html)

## Verification and acceptance

Use synthetic students and marks for development and demonstrations. The original register photographs are included in the teaching repository at the user's request as layout references; do not turn their handwritten student information into application seed data. Verification must establish the following observable outcomes:

| Scenario | Required result |
| --- | --- |
| Two faculty accounts | Neither can read, alter or download the other's register by changing a URL or request |
| Paste a reordered marks list | Scores attach to the correct USN; unknown or duplicate USNs are flagged |
| P, P, A, P, A | Printed running entries are 1, 2, A, 3, A; percentage is 60 |
| Two periods on one date | One period can be absent and the other present; a whole-day selection affects both visibly |
| Future and unconfirmed sessions | No assumed presence and no contribution to completed attendance percentages |
| Test replaces a teaching period | Exactly one attendance session is counted; the original topic remains outstanding |
| Test percentage | Includes the test and all applicable conducted sessions through that date, excluding later dates |
| Timetable changes midway through term | Earlier recorded events stay intact; outstanding topics use the appropriate effective timetable |
| Holiday entered for a recorded day | Conflict is visible; attendance is retained until reconciliation; all results update after resolution |
| Cancel and add a replacement | Cancelled attendance leaves the active denominator; replacement attendance starts unmarked |
| Weighted scores with unequal maxima | Normalisation and the configured rule produce the expected result without premature rounding |
| Missing mark or invalid weights | Result stays pending or rule is rejected; no silent zero or weight redistribution |
| Best two of three | Normalised scores determine selection; a missing third mark does not produce a final result |
| Concurrent browser edits | A stale save produces a conflict instead of overwriting a newer edit |
| Repeated save or schedule rebuild | No duplicate sessions, students or marks |
| Restart and restore | Saved work survives restart, and a verified backup restores a known register accurately |
| DOCX layout | Correct sizes, complete fields, aligned rows, red absence marks, no clipping and correct continuation counts |
| Physical booklet assembly | Printed full and half-width leaves fit between the existing covers and expose the intended columns in order |

Run calculation tests and integration tests against the same services used by the UI and export. Inspect rendered Word pages for both typical and long-text examples, empty and full blocks, and more than 75 sessions. Exercise the Windows launcher and Word printing on Windows before describing the Windows deployment and physical print output as verified.

## Boundaries of the first release

The first release covers theory registers matching the supplied six-assessment booklet. It does not include OCR, uploaded-document extraction, a student portal, biometric attendance, public internet hosting, automatic messages to students, or editable programming formulas. Changes to the number of assessment headings or a different laboratory register layout require a separate print-template extension.

The exact printer model, duplex feed direction, fonts available on the Windows machine and binding margins are installation and calibration inputs. They do not change the agreed page dimensions or the requirement to reproduce the booklet. Do not substitute a generic A4 report when those checks remain unfinished.

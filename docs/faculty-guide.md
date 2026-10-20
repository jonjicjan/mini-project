# Faculty workflow

The manual-entry workflow is organised by department/branch, semester, section and subject. Create a separate register for each subject and section. Records remain private to the owning faculty account.

1. **Register details.** Enter the department, section, subject, academic year and term dates. Open **Students, attendance & marks** to reach the register tabs.
2. **Students.** Add USN, name, order and eligibility dates. A late joiner's eligibility begins on their joining date. An end date is inclusive. Use Edit for a USN correction so the permanent student ID and attendance remain linked. Eligibility changes are blocked once attendance exists; do not replace a student to work around this.
3. **Lessons.** Add numbered topics and optional original dates, periods, reported execution dates and remarks. Original dates are retained. Imported historical dates create sessions with unmarked attendance. Their provisional 09:00–10:00 time must be confirmed/corrected under Classes & tests before attendance can be recorded. Future execution dates are rejected.
4. **Timetable.** Enter weekly periods with start/end times and effective dates for this register. End an old entry before adding a replacement that overlaps it. Overlap validation covers the faculty's other registers too. Under **Classes & tests**, preview scheduling from a chosen date and explicitly apply it. Scheduling skips holidays and occupied classes, reports topics that cannot fit in the term, and preserves historical/fixed classes. It does not assume attendance.
5. **Classes and tests.** Add exceptional classes manually. For an internal test, select Test 1, 2 or 3 and its start/end time. A test spanning multiple periods counts as one attendance event. Select a planned, unrecorded class only when it should be replaced; its lesson remains available for rescheduling. Cancelling retains existing history. Correcting a conducted class requires a reason and retains the permanent session ID.
6. **Holidays.** Add a date or date range. Existing classes on those dates become conflicts rather than silently moving. Review each conflict and either keep the actual class with a reason or cancel it while retaining attendance history. Date/time corrections are made in Classes & tests; then resolve the related conflict explicitly.
7. **Attendance.** The running grid shows counts, red A for absence, a dash outside eligibility, and blank unmarked/future cells. Choose a class/date to edit its student statuses. **Save attendance** preserves entered statuses. **Complete class** is a separate action that records eligible unmarked students as present and preserves explicit absences. Future/cancelled classes cannot be completed. Percentages include conducted classes through today and are marked provisional when applicable attendance is missing or a conflict remains.
8. **Assessment rules and marks.** Confirm this register's maxima, assignment/test contribution percentages, aggregation method, best-N count and final rounding. Defaults are examples, not an institutional policy. Weights must total exactly 100%. Mark entry accepts a number, `AB` (absent), or `CLEAR` (missing). Blank pasted cells preserve saved marks. Zero and missing are different. Missing required candidates keep the final result pending, including best-N candidates. Rules cannot lower a maximum below an already saved mark. Marks do not automatically change attendance.
9. **Word exports.** Choose a cutoff date. Current assignments are retained; tests after the cutoff remain blank. Each issued DOCX is saved with its immutable data snapshot and checksum. The same download returns the same document after later edits. Drafts allow missing results and fit warnings; review the warnings listed below the download link before printing. A final export is blocked until those warnings are resolved. Follow the separate print guide for custom paper sizes.

## Pasting rows

Manual entry is always available. For batches, copy from an Excel/Word table or use CSV. Choose tabs or commas and set the column order. Preview first; Apply saves the entire batch or none. Existing rows omitted from a paste are retained. The preview does not write to the database.

Examples with comma-separated input:

```text
usn,name,eligible_from,eligible_to
DEMO001,Sample Student,2026-08-01,
DEMO002,Another Student,2026-09-01,
```

```text
original_number,topic,original_date,original_period,reported_execution_date,remarks
1,Introduction,2026-08-03,1,,
2,"Design, examples and discussion",2026-08-05,2,,
```

```text
usn,A1,A2,A3,T1,T2,T3
DEMO002,20,,,AB,,
DEMO001,22.5,CLEAR,,,,
```

Dates accept `YYYY-MM-DD` and four-digit-year `DD/MM/YYYY`; two-digit years are rejected. USNs stay text, including leading zeros. Ordinary imports update students by USN without changing their order or permanent ID; lesson imports match the original lesson number.

## Saves and recovery

Saves are explicit in this manual release. A revision conflict means someone saved a newer version; attempted values are not silently applied. Copy/review your edits and reload before retrying. Repeated accepted operations return the existing receipt instead of duplicating data.

Administrators can create and download verified whole-system backups from **System backups**. These contain every faculty member's records and must be kept in approved storage. The production supervisor creates a missed daily backup at startup and checks once a minute for the next daily backup; it retains the latest 30 successful daily dates. Keep an additional copy off the host PC. Restores are offline maintenance operations that retain a recovery backup and invalidate login sessions; see the Windows setup guide.

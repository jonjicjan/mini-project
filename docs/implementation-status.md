# Implementation status

Updated 5 October 2026. The manual-entry release is available for local use and evaluation. The approved design remains the full target; the feature set below does not imply that every original plan task is complete.

## Working application

- Faculty login, administrator account management, throttling, session revocation, owner-private registers, search, archive/restore and audit history.
- Separate registers by department/branch, semester, section and subject. Student and lesson forms, editable records, and signed tab/CSV paste previews with atomic apply. Marks can also be pasted. Omitted rows are retained.
- Effective-dated weekly timetable entries per register, faculty-wide overlap checks, preview/apply future scheduling, exceptional classes, three internal tests and holiday conflict resolution. Recorded history and stable identifiers are preserved.
- Explicit attendance recording and separate class completion, eligibility dates, running attendance, cumulative percentages, unmarked/provisional results and historical time confirmation.
- Per-register assessment rules, decimal marks, absent/missing distinction, configurable maxima, weights, mean/sum/best-N aggregation and final rounding.
- Editable Word exports from saved records, cutoff-aware calculations, warning review, immutable snapshots and protected repeat downloads. Issued document bytes are stored in SQLite and included in database backups.
- Verified online SQLite backups, administrator backup downloads, offline restore with recovery backup and session invalidation, and retention of 30 valid daily backup groups.
- Windows setup, Waitress/Caddy supervision, daily backups, optional logon startup, stop and installation-check scripts. Production settings require explicit hosts, data location, secret and HTTPS.

Saves are explicit. See the [faculty guide](faculty-guide.md) for the actual workflow and [verification evidence](verification.md) for checks performed.

## Current machine

The development database is `var/register.sqlite3`. It was backed up before applying all feature migrations on 5 October. Existing data was preserved; no demonstration students were added to it. The local app responds at http://127.0.0.1:8000/ and its health and login endpoints returned HTTP 200.

All 88 tests passed, covering unit, integration and Microsoft Edge browser workflows. Django model and production configuration checks passed, with no missing migrations. Word rendered a saved-record export to 12 pages, all visually inspected.

## Before college production use

Select the host and access scope, then follow the [Windows setup guide](windows-setup.md). Caddy installation, certificate trust, firewall/access configuration, optional startup registration and second-PC HTTPS login have not been activated or verified on a college host. Production configuration checks are not a deployed-server acceptance test.

Confirm the institution's assessment rules, obtain approved branding, and check actual-size booklet printing and physical assembly on the intended printer. Keep backups on a separate protected device/location and rehearse recovery on the intended host. Independent review and planned Git commits remain pending.

## Remaining original-design work

The current release uses per-register timetable entries and rule snapshots. Shared faculty timetable version management, reusable marking-template libraries, day/week/month calendar views, multi-register holiday workflows and resilient attendance autosave remain outside this manual release. Paste imports cover students, lessons and marks; timetable entries are entered manually. The original 12-task plan should not be marked complete on the strength of this release.

## Implementation notes

Django 5.2 uses SQLite with immediate transactions. Domain identifiers are UUIDs; account identifiers are Django integers. Every register mutation rechecks ownership and revision inside its transaction, records an audit event, and stores an idempotency receipt. Stale changes return conflicts instead of overwriting newer values. Foreign records return 404. Bounded retries handle transient database contention.

Tests use isolated databases and synthetic records. Runtime dependencies are pinned. The repository does not hard-code the developer's bundled Python path; another host needs its own supported Python installation. The development server remains loopback-only and must not be used as the college production server.

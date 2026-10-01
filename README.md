# Faculty Attendance Register

This repository is the project handoff for students developing a faculty attendance-register application. It contains the approved design, a detailed implementation plan and 24 photographs of the existing register. Application code has not been created.

## Start here

1. Read the [approved design](docs/superpowers/specs/2026-10-01-attendance-register-design.md) for the required behaviour and acceptance criteria.
2. Follow the [implementation plan](docs/superpowers/plans/2026-10-01-attendance-register.md), which divides the work into 12 testable tasks with files, interfaces, checks and milestones.
3. Inspect the photographs at the repository root before designing the Word output. Numbered images follow the supplied page order, but some show folded or overlapping leaves.

The `docs/superpowers/` path preserves the original document location. The plan is written for student developers and requires no particular AI tool.

## Application to build

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

# Booklet export and print guide

Updated 5 October 2026. Registers now export editable Word documents from saved students, lessons, attendance and marks through the **Word exports** tab. Select a cutoff date, review draft warnings and download the issued document. Issued documents retain their original snapshot after subsequent record edits. Physical printer calibration and institutional acceptance remain pending.

The synthetic geometry sample below remains available separately. Live exports show their cutoff and source revision; draft exports are labelled DRAFT. Assignment and test contribution columns contain weighted contributions to the final maximum, rather than raw group totals.

## Generate the sample

```powershell
.\.venv\Scripts\python.exe manage.py render_booklet_fixture --output artifacts/booklet-sample.docx
```

Run from the project directory after development setup. The command reads `tests/fixtures/booklet_synthetic.json`, writes a DOCX and an adjacent `.warnings.json` report, and never queries register records. The supplied fixture produces 12 printed sides with no fit warnings: 20 synthetic students, 75 session columns, three sample lessons, illustrative attendance and assignment values, and a weekly timetable. Attendance after the sample cutoff is blank. This is not a real teaching schedule.

The first three lesson pages provide 20 + 25 + 25 = 70 rows; additional lessons produce 25-row continuation pages. Every attendance block contains 20 student rows. Students 21 and 61 start new blocks. Session 76 starts another complete 75-column set for every student block. Unused capacity remains blank. Assessment values appear only in the last session set. Timetables exceeding nine columns continue on another page.

## Logical panels and physical leaves

The photographs contain overlapping leaves. In `IMG_1643.JPG`–`IMG_1646.JPG`, parts of the final assessment sheet are visible behind narrower leaves. Treating each photograph as a single printed side would duplicate columns. This reconstruction covers sessions 1–75 exactly once for students 1–20:

| Sample page | Content | Width × height | Physical interpretation | Reference |
| --- | --- | --- | --- | --- |
| 1 | Lesson rows 1–20 and heading | 210 × 307 mm | Full side | `page2.JPG` |
| 2 | Lesson rows 21–45 | 210 × 307 mm | Full side | `IMG_1640.JPG` |
| 3 | Lesson rows 46–70 and signatures | 210 × 307 mm | Full side | `IMG_1641.JPG` |
| 4 | Roster and sessions 1–10 | 210 × 307 mm | Full opening roster side | `IMG_1642.JPG` |
| 5 | Sessions 11–20 | 105 × 307 mm | Half leaf 1, recto | `IMG_1643.JPG` |
| 6 | Sessions 21–30 | 105 × 307 mm | Half leaf 1, verso | `IMG_1644.JPG`, left |
| 7 | Sessions 31–40 | 105 × 307 mm | Half leaf 2, recto | `IMG_1644.JPG`, right |
| 8 | Sessions 41–50 | 105 × 307 mm | Half leaf 2, verso | `IMG_1645.JPG`, left |
| 9 | Sessions 51–60 | 105 × 307 mm | Half leaf 3, recto | `IMG_1645.JPG`, right |
| 10 | Sessions 61–70 | 105 × 307 mm | Half leaf 3, verso | `IMG_1646.JPG`, left |
| 11 | Sessions 71–75 and assessments | 210 × 307 mm | Full closing assessment side | `IMG_1647.JPG` |
| 12 | Weekly timetable and signatures | 210 × 307 mm | Separate interior insert | `inside of back cover.JPG` |

`IMG_1648.JPG`–`IMG_1653.JPG` and `IMG_1654.JPG`–`IMG_1659.JPG` repeat this pattern for later student blocks. The recto/verso pairs are an assembly inference, not verified printer feed directions. Full-side backs, hinges, binding offsets and duplex imposition are not encoded. The timetable is an interior insert; all covers are omitted.

## Dimensions and fidelity

**Authoritative outer dimensions:** full 210 × 307 mm; half 105 × 307 mm. These are custom sizes, not A4. DOCX dimensions round to the nearest integer twip.

**Initial reconstruction measurements, pending physical comparison:**

| Measurement | Value |
| --- | --- |
| Top and bottom margins | 10 mm |
| Full-page left and right margins | 10 mm |
| Half-page left and right margins | 5 mm |
| Full and half table width | 190 mm and 95 mm |
| Roster portion | 95 mm: serial 8, USN 30, name 57 |
| Attendance column width | 9.5 mm |
| Attendance body top from paper top | 80 mm |
| Each of 20 student rows | 8.3 mm, rounded to 471 twips |
| Body bottom | Approximately 246 mm |
| Absent / present footer rows | 6 mm each |
| Initials / signature bands | 12 mm / 16 mm |

All attendance sides share a 25 mm institution band, 20 mm metadata band and 25 mm session header. Header rows show class number, period and day/month. Footer count rows show absent, then present; their labels appear on the roster panel and align with continuation panels. Totals are per student block.

Institution names and affiliation wording are transcribed from the references. The circular seal and stylised logo artwork are not reproduced; an approved clean logo asset is still needed. No photographs, handwritten names, signatures or student records are embedded. This is a geometry reconstruction, not a certified exact facsimile.

Fixed, non-splitting rows preserve leaf alignment. Word compatibility mode 15 and zero vertical cell padding prevent row-height inflation observed in the first render. Oversized text receives a visible `[See fit warning]` or `[!]` marker and a warning containing the full original value. Resolve warnings before printing. The conservative text-fit estimate does not replace visual checking after content or font changes.

## Print and calibrate

1. Open the DOCX in desktop Word. Confirm 12 pages and the mixed custom paper sizes.
2. Configure 210 × 307 mm and 105 × 307 mm stock in the intended printer driver. Print at actual size / 100%; disable fit-to-paper, booklet scaling and multiple-pages-per-sheet. If unsupported, use a verified actual-size placement/cutting workflow on larger stock. Do not shrink to A4.
3. First print full pages 1–4 and 11–12 separately from half pages 5–10, simplex with blank backs. The file adds no blank backs and performs no duplex imposition.
4. Measure paper and grids. Full table width should be 190 mm, half width 95 mm, and the first student row should start 80 mm below the top. Align pages 4, 5 and 11 and compare first and twentieth rows. Record printer offsets before changing template dimensions.
5. Test half-leaf pairs 5/6, 7/8 and 9/10 on scrap stock. Mark the leading edge and determine the feed/flip setting experimentally. Assemble with roster and assessment sheets and check alignment as each leaf turns.
6. Check red `A`, non-member dashes, blank future cells, empty signature spaces and assessment headings. Compare against a blank physical booklet if available.

Record Word build, printer model, driver, stock, scale, feed/flip setting, measured offsets, assembly method and faculty sign-off. **Physical checks remain pending.** The sample itself supplies the calibration grid; no calibration page is inserted into the booklet.

## Rendering evidence

On 2 October 2026, **Microsoft Word 16.0, build 16.0.20430** rendered the final sample to **12 PDF pages**: six full-width and six half-width. All 12 PNGs were opened at their native 144-dpi render size and inspected for clipping, alignment, sequence and signature placement. There were no overflow pages or fit warnings. PDF dimensions were 595.32 × 870.24 pt and 297.60 × 870.24 pt, consistent with the required sizes after renderer rounding.

Exact Word command from the workspace:

```powershell
powershell -NoProfile -STA -ExecutionPolicy Bypass -File scripts/windows/render-booklet-word.ps1 -InputDocx artifacts/booklet-sample.docx -OutputPdf artifacts/booklet-final-render/booklet-sample.pdf
```

The script creates a separate hidden Word instance, opens the sample read-only with macros disabled, exports PDF and closes its instance. Word is a developer verification tool, not a production web-server dependency.

The bundled `render_docx.py` was attempted first and failed with `FileNotFoundError: LibreOffice soffice.exe was not found on PATH`. After diagnosing the missing renderer, Word was used as the plan permits. PNG rendering and page-size checks used bundled Poppler:

```powershell
& 'C:/Users/Jamal Khan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe' -r 144 -png artifacts/booklet-final-render/booklet-sample.pdf artifacts/booklet-final-render/page
& 'C:/Users/Jamal Khan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdfinfo.exe' -f 1 -l 12 artifacts/booklet-final-render/booklet-sample.pdf
```

PDFs and PNGs under `artifacts/` are local QA intermediates. The deliverable is the editable DOCX. Snapshot capture, cutoff calculations, protected downloads and repeatable issued exports are now integrated. The renderer consumes prepared display values from the attendance and assessment services.

On 5 October 2026, an export created through the browser from saved synthetic application records was rendered with Microsoft Word 16.0, build 16.0.20430. All 12 pages were inspected as 120-dpi PNGs. The roster, red absence mark, saved assignment mark, contribution headings and dated draft footer were present without clipping or extra pages. This verifies the saved-record workflow, not physical printer calibration.

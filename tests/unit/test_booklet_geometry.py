import copy
import json
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree

from exports.docx_render import render_booklet
from exports.geometry import mm_to_twips
from exports.leaves import plan_leaves

FIXTURE = Path(__file__).parents[1] / "fixtures" / "booklet_synthetic.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@pytest.mark.parametrize("students,blocks", [(0, 1), (20, 1), (21, 2), (61, 4)])
@pytest.mark.parametrize("sessions,batches", [(0, 1), (75, 1), (76, 2), (151, 3)])
def test_each_column_once_per_student_block(students, blocks, sessions, batches):
    leaves = plan_leaves(students, sessions)
    assert len(leaves) == blocks * batches * 8
    for block in range(blocks):
        panels = [leaf for leaf in leaves if leaf.student_start == block * 20]
        assert {leaf.student_end for leaf in panels} == {block * 20 + 20}
        columns = [c for leaf in panels for c in range(leaf.session_start, leaf.session_end)]
        assert columns == list(range(batches * 75))
        for leaf in panels:
            assert leaf.height_mm == Decimal(307)
            assert leaf.width_mm == Decimal(105 if leaf.kind == "continuation" else 210)
        assert [leaf.side for leaf in panels[:8]] == [
            "full",
            "recto",
            "verso",
            "recto",
            "verso",
            "recto",
            "verso",
            "full",
        ]


@pytest.mark.parametrize("counts", [(-1, 1), (1, -1), (1.5, 2), (True, 1)])
def test_invalid_counts(counts):
    with pytest.raises(ValueError):
        plan_leaves(*counts)


def read_xml(target):
    with ZipFile(target) as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def test_render_geometry_rows_color_and_blank_signatures(tmp_path):
    snapshot = json.loads(FIXTURE.read_text())
    original = copy.deepcopy(snapshot)
    target = tmp_path / "sample.docx"
    assert render_booklet(snapshot, target) == []
    assert snapshot == original
    root = read_xml(target)
    sizes = root.xpath("//w:sectPr/w:pgSz", namespaces=NS)
    assert len(sizes) == 12  # three lesson sides, eight attendance sides, timetable
    expected_widths = [210, 210, 210, 210, 105, 105, 105, 105, 105, 105, 210, 210]
    for size, width in zip(sizes, expected_widths, strict=True):
        assert abs(int(size.get(f"{{{NS['w']}}}w")) - mm_to_twips(width)) <= 1
        assert abs(int(size.get(f"{{{NS['w']}}}h")) - mm_to_twips(307)) <= 1
    rows = root.xpath("//w:tr", namespaces=NS)
    assert all(row.find("w:trPr/w:cantSplit", NS) is not None for row in rows)
    red_runs = root.xpath('//w:r[w:rPr/w:color[@w:val="FF0000"]]/w:t/text()', namespaces=NS)
    assert red_runs and set(red_runs) == {"A"}
    texts = root.xpath("//w:t/text()", namespaces=NS)
    assert any("Signature of Faculty" in text for text in texts)
    assert any("Signature of HOD" in text for text in texts)
    assert root.xpath("//w:drawing | //w:pict", namespaces=NS)
    # Twenty identical body row heights on every attendance panel, even blank rows.
    for table in root.xpath("/w:document/w:body/w:tbl", namespaces=NS)[3:11]:
        body = table.xpath('w:tr[w:trPr/w:trHeight[@w:val="471"]]', namespaces=NS)
        assert len(body) == 20


def test_unfittable_name_returns_full_text_warning(tmp_path):
    snapshot = json.loads(FIXTURE.read_text())
    long_name = "Extremelylongstudentname " * 20
    snapshot["students"][0]["name"] = long_name
    target = tmp_path / "long.docx"
    warnings = render_booklet(snapshot, target)
    assert any(long_name in warning and "name" in warning for warning in warnings)
    assert "[See fit warning]" in read_xml(target).xpath("//w:t/text()", namespaces=NS)


def test_reject_unknown_snapshot_before_writing(tmp_path):
    target = tmp_path / "bad.docx"
    with pytest.raises(ValueError, match="schema"):
        render_booklet({"schema_version": 999}, target)
    assert not target.exists()


def test_render_student_and_session_continuations_without_lost_values(tmp_path):
    snapshot = json.loads(FIXTURE.read_text())
    snapshot["students"].append(
        {"id": "student-21", "serial": 21, "usn": "DEMO021", "name": "Continuation Student"}
    )
    snapshot["sessions"].append(
        {
            "id": "session-76",
            "display_number": 76,
            "date": "2026-10-17",
            "period": "2",
            "kind": "lesson",
            "status": "conducted",
        }
    )
    snapshot["attendance"]["student-21"] = {"cells": {"session-76": "A"}}
    snapshot["assessments"]["students"]["student-21"] = {"display": ["19"] + [""] * 12}
    target = tmp_path / "overflow.docx"
    assert render_booklet(snapshot, target) == []
    root = read_xml(target)
    assert len(root.xpath("//w:sectPr", namespaces=NS)) == 36
    tables = root.xpath("/w:document/w:body/w:tbl", namespaces=NS)
    # Each block has two batches. Assessments print only after the final batch.
    first_assessment = tables[10].xpath(".//w:t/text()", namespaces=NS)
    assert "20" not in first_assessment
    second_block_roster = tables[27]
    assert "Continuation Student" in second_block_roster.xpath(".//w:t/text()", namespaces=NS)
    red = second_block_roster.xpath(
        './/w:r[w:rPr/w:color[@w:val="FF0000"]]/w:t/text()', namespaces=NS
    )
    assert "A" in red
    rows = second_block_roster.xpath('w:tr[w:trPr/w:trHeight[@w:val="471"]]', namespaces=NS)
    assert len(rows) == 20
    assert all(not row.xpath(".//w:t", namespaces=NS) for row in rows[1:])

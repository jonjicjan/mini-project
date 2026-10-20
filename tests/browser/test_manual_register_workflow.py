from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.browser]
ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts" / "screenshots"


def test_manual_department_section_workflow(page, live_server, faculty, register):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/login/")
    page.get_by_label("Username").fill("teacher1")
    page.get_by_label("Password", exact=False).fill("Synthetic-passphrase-47")
    page.get_by_role("button", name="Sign in").click()
    base = f"{live_server.url}/registers/{register.pk}/work/"
    page.goto(base + "students/")
    for key, value in {
        "usn": "DEMO001",
        "name": "Synthetic Student",
        "serial_number": "1",
        "eligible_from": "2026-08-01",
    }.items():
        page.locator(f"#id_{key}").fill(value)
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
    expect(page.locator("table").get_by_text("Synthetic Student", exact=True)).to_be_visible()
    page.goto(base + "lessons/")
    page.locator("#id_original_number").fill("1")
    page.locator("#id_topic").fill("Introduction to software design")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
    page.goto(base + "sessions/")
    page.locator("#id_scheduled_date").fill("2026-10-01")
    page.locator("#id_period").fill("1")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
    page.goto(base + "attendance/")
    page.get_by_label("Attendance for DEMO001").select_option("absent")
    page.get_by_role("button", name="Complete class", exact=True).click()
    expect(page.get_by_text("Class completed.", exact=False)).to_be_visible()
    page.reload()
    expect(page.get_by_label("Attendance for DEMO001")).to_have_value("absent")
    expect(page.get_by_text("0 / 1", exact=True)).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "attendance-manual-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "attendance-manual-mobile.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(base + "rules/")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
    page.goto(base + "marks/")
    page.locator("#id_usn").select_option("DEMO001")
    page.locator("#id_A1").fill("20")
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved successfully.", exact=True)).to_be_visible()
    expect(page.locator("table").get_by_text("20.000", exact=True)).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "marks-manual-desktop.png"), full_page=True)
    page.goto(base + "exports/")
    page.get_by_role("button", name="Generate Word document").click()
    expect(page.get_by_role("link", name="Download Word", exact=False)).to_be_visible(timeout=30000)
    with page.expect_download() as download:
        page.get_by_role("link", name="Download Word", exact=False).click()
    assert download.value.suggested_filename.endswith(".docx")
    download.value.save_as(str(ARTIFACTS.parent / "actual-records-demo.docx"))

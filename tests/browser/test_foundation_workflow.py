import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.browser]
ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts" / "screenshots"


def sign_in(page, live_server, username, password):
    page.goto(f"{live_server.url}/login/")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password", exact=False).fill(password)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading", name="My registers.", exact=True)).to_be_visible()


def test_register_workflow_conflict_archive_and_responsive_layout(
    page, context, live_server, faculty
):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(f"{live_server.url}/login/")
    expect(page.locator(".login-panel")).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "login-desktop.png"), full_page=True)
    sign_in(page, live_server, "teacher1", "Synthetic-passphrase-47")
    page.get_by_role("link", name="Create your first register").click()
    values = {
        "subject_name": "Software Engineering",
        "subject_code": "BCS501",
        "academic_year": "2026–2027",
        "faculty_name": "Dr Asha Rao",
        "branch": "AI & ML",
        "semester": "V",
        "section": "B",
        "term_start": "2026-08-01",
        "term_end": "2026-12-31",
    }
    for key, value in values.items():
        page.locator(f"#id_{key}").fill(value)
    page.get_by_role("button", name="Create register").click()
    expect(page.get_by_text("Register saved.", exact=True)).to_be_visible()
    register_url = page.url
    stale = context.new_page()
    stale.goto(register_url)
    page.locator("#id_subject_name").fill("Software Engineering & Project Management")
    expect(page.get_by_text("Unsaved changes", exact=True)).to_be_visible()
    page.get_by_role("button", name="Save changes").click()
    page.reload()
    expect(page.locator("#id_subject_name")).to_have_value(
        "Software Engineering & Project Management"
    )
    stale.locator("#id_subject_name").fill("Stale edit must not overwrite")
    stale.get_by_role("button", name="Save changes").click()
    expect(stale.get_by_role("heading", name="Your changes were not saved")).to_be_visible()
    expect(stale.locator("#id_subject_name")).to_have_value("Stale edit must not overwrite")
    stale.close()
    page.screenshot(path=str(ARTIFACTS / "register-desktop.png"), full_page=True)
    page.get_by_role("link", name="Back to registers", exact=True).click()
    expect(
        page.get_by_role("heading", name="Software Engineering & Project Management")
    ).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / "dashboard-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ARTIFACTS / "dashboard-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("link", name="Open Software Engineering & Project Management").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("link", name="Archive register").click()
    page.get_by_role("button", name="Archive register").click()
    expect(page.get_by_role("heading", name="Your next term starts here")).to_be_visible()
    page.get_by_role("link", name=re.compile("Archived")).click()
    page.get_by_role("link", name="Open Software Engineering & Project Management").click()
    page.get_by_role("link", name="Restore register").click()
    page.get_by_role("button", name="Restore register").click()
    expect(
        page.get_by_role("heading", name="Software Engineering & Project Management")
    ).to_be_visible()


def test_account_admin_and_foreign_register_isolation(
    page, live_server, administrator, other_faculty, register
):
    sign_in(page, live_server, "administrator", "Synthetic-admin-passphrase-47")
    page.get_by_role("link", name="Faculty accounts", exact=False).click()
    page.locator("#id_username").fill("browser-faculty")
    page.locator("#id_display_name").fill("Dr Browser Sample")
    page.locator("#id_temporary_password").fill("Browser-synthetic-secret-53")
    page.get_by_role("button", name="Create faculty account").click()
    expect(page.get_by_role("cell", name="Dr Browser Sample", exact=True)).to_be_visible()
    page.get_by_role("link", name="Reset password for browser-faculty", exact=True).click()
    page.locator("#id_password").fill("Browser-replacement-secret-53")
    page.get_by_role("button", name="Reset password", exact=True).click()
    page.get_by_role("button", name="Sign out").click()
    sign_in(page, live_server, "browser-faculty", "Browser-replacement-secret-53")
    response = page.goto(f"{live_server.url}/registers/{register.pk}/")
    assert response.status == 404
    assert "Software Engineering" not in page.content()

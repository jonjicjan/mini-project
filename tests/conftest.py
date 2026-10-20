from datetime import date

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def faculty(db):
    return get_user_model().objects.create_user(
        username="teacher1", password="Synthetic-passphrase-47", display_name="Dr Asha Rao"
    )


@pytest.fixture
def other_faculty(db):
    return get_user_model().objects.create_user(
        username="teacher2", password="Synthetic-passphrase-48", display_name="Dr Dev Shah"
    )


@pytest.fixture
def administrator(db):
    return get_user_model().objects.create_superuser(
        username="administrator", password="Synthetic-admin-passphrase-47"
    )


@pytest.fixture
def register_values():
    return dict(
        academic_year="2026–2027",
        semester="V",
        branch="AI & ML",
        section="B",
        subject_code="BCS501",
        subject_name="Software Engineering",
        faculty_name="Dr Asha Rao",
        term_start=date(2026, 8, 1),
        term_end=date(2026, 12, 31),
    )


@pytest.fixture
def register(faculty, register_values):
    from registers.models import Register

    return Register.objects.create(owner=faculty, **register_values)

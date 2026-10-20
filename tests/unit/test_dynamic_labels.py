from decimal import Decimal
import pytest

from assessments.calculations import default_rule
from exports.snapshot import build_export_snapshot


@pytest.mark.django_db
def test_dynamic_assessment_labels_default_rule(faculty, register):
    # Default rule: assignments 40% (mean_normalised), tests 60% (mean_normalised), final_max 50
    snapshot = build_export_snapshot(faculty, register.pk, through=register.term_end, draft=True)
    assessments = snapshot["assessments"]
    assert assessments["maxima"]["assignment"] == "20"
    assert assessments["maxima"]["test"] == "30"
    assert assessments["maxima"]["overall"] == "50"
    assert assessments["labels"][3] == "Assign.\ncontrib."
    assert assessments["labels"][11] == "Test\ncontrib."
    assert assessments["preview_labels"][3] == ["Assign. contrib.", "/20"]
    assert assessments["preview_labels"][11] == ["Test contrib.", "/30"]


@pytest.mark.django_db
def test_dynamic_assessment_labels_best_n(faculty, register):
    # Configure rule with best_n for both assignments (best-2) and tests (best-2)
    from assessments.services import save_rule

    rule = default_rule()
    rule["components"][0].update(aggregation="best_n", best_n=2)
    rule["components"][1].update(aggregation="best_n", best_n=2)
    save_rule(
        faculty,
        register.pk,
        definition=rule,
        expected_revision=register.revision,
        request_id="11111111-1111-1111-1111-111111111111",
    )
    register.refresh_from_db()

    snapshot = build_export_snapshot(faculty, register.pk, through=register.term_end, draft=True)
    assessments = snapshot["assessments"]
    assert assessments["labels"][3] == "Assign.\nBest-2"
    assert assessments["labels"][11] == "Test\nBest-2"
    assert assessments["preview_labels"][3] == ["Assign. Best-2", "/20"]
    assert assessments["preview_labels"][11] == ["Test Best-2", "/30"]


@pytest.mark.django_db
def test_dynamic_assessment_labels_sum_ratio(faculty, register):
    from assessments.services import save_rule

    rule = default_rule()
    rule["components"][0].update(aggregation="sum_ratio")
    rule["components"][1].update(aggregation="sum_ratio")
    save_rule(
        faculty,
        register.pk,
        definition=rule,
        expected_revision=register.revision,
        request_id="22222222-2222-2222-2222-222222222222",
    )
    register.refresh_from_db()

    snapshot = build_export_snapshot(faculty, register.pk, through=register.term_end, draft=True)
    assessments = snapshot["assessments"]
    assert assessments["labels"][3] == "Assign.\nScore"
    assert assessments["labels"][11] == "Test\nScore"
    assert assessments["preview_labels"][3] == ["Assign. Score", "/20"]
    assert assessments["preview_labels"][11] == ["Test Score", "/30"]

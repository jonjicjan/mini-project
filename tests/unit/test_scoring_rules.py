from decimal import Decimal

import pytest

from assessments.calculations import calculate_score, default_rule, validate_rule


@pytest.mark.parametrize(
    "method,expected",
    [
        ("mean_normalised", Decimal("20")),
        ("sum_ratio", Decimal("17.86")),
        ("best_n", Decimal("25")),
    ],
)
def test_unequal_maxima(method, expected):
    rule = default_rule()
    rule["rounding"] = "two_decimals_half_up"
    rule["assessments"].update(T1="20", T2="50")
    rule["components"] = [
        {
            "id": "tests",
            "kind": "group",
            "assessment_keys": ["T1", "T2"],
            "weight_percent": "100",
            "aggregation": method,
            "best_n": 1,
        }
    ]
    result = calculate_score(
        rule, {"T1": {"status": "scored", "value": "10"}, "T2": {"status": "scored", "value": "15"}}
    )
    assert result["rounded"] == expected


def test_best_n_missing_candidate_pending_and_zero_weight_ignored():
    rule = default_rule()
    rule["components"][0]["weight_percent"] = "0"
    rule["components"][1].update(weight_percent="100", aggregation="best_n", best_n=2)
    marks = {"T1": {"status": "scored", "value": "25"}, "T2": {"status": "absent", "value": None}}
    assert calculate_score(rule, marks)["pending_keys"] == ["T3"]
    marks["T3"] = {"status": "scored", "value": "20"}
    assert calculate_score(rule, marks)["rounded"] == Decimal("45")


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_maxima(value):
    rule = default_rule()
    rule["assessments"]["A1"] = value
    assert validate_rule(rule)

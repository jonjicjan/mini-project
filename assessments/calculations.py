from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation

KEYS = ("A1", "A2", "A3", "T1", "T2", "T3")
ROUNDING = {
    "whole_half_up": ("1", ROUND_HALF_UP),
    "one_decimal_half_up": ("0.1", ROUND_HALF_UP),
    "two_decimals_half_up": ("0.01", ROUND_HALF_UP),
    "whole_ceiling": ("1", ROUND_CEILING),
    "whole_floor": ("1", ROUND_FLOOR),
}


def decimal(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Use a finite numeric value.") from None


def default_rule():
    return {
        "schema_version": 1,
        "final_maximum": "50",
        "rounding": "whole_half_up",
        "assessments": {key: "25" for key in KEYS},
        "components": [
            {
                "id": "assignments",
                "kind": "group",
                "assessment_keys": list(KEYS[:3]),
                "weight_percent": "40",
                "aggregation": "mean_normalised",
            },
            {
                "id": "tests",
                "kind": "group",
                "assessment_keys": list(KEYS[3:]),
                "weight_percent": "60",
                "aggregation": "mean_normalised",
            },
        ],
    }


def validate_rule(definition):
    try:
        if definition["schema_version"] != 1 or definition["rounding"] not in ROUNDING:
            raise ValueError("Unsupported scoring rule or rounding.")
        if not 0 < decimal(definition["final_maximum"]) <= 1_000_000:
            raise ValueError("Final maximum must be positive and at most 1,000,000.")
        if set(definition["assessments"]) != set(KEYS):
            raise ValueError("Configure maxima for A1–A3 and T1–T3.")
        if any(not 0 < decimal(v) <= 1_000_000 for v in definition["assessments"].values()):
            raise ValueError("Every assessment maximum must be positive and at most 1,000,000.")
        used, ids, weight = set(), set(), Decimal(0)
        for component in definition["components"]:
            keys = component["assessment_keys"]
            w = decimal(component["weight_percent"])
            if (
                not 0 <= w <= 100
                or not keys
                or set(keys) - set(KEYS)
                or len(keys) != len(set(keys))
            ):
                raise ValueError("Invalid component keys or weight.")
            if component["id"] in ids:
                raise ValueError("Component names must be unique.")
            ids.add(component["id"])
            if w and used.intersection(keys):
                raise ValueError("An assessment cannot contribute twice.")
            if w:
                used.update(keys)
            aggregation = component["aggregation"]
            if aggregation not in ("individual", "mean_normalised", "sum_ratio", "best_n"):
                raise ValueError("Unknown aggregation method.")
            if aggregation == "individual" and len(keys) != 1:
                raise ValueError("An individual component needs one assessment.")
            if aggregation == "best_n" and (
                type(component.get("best_n")) is not int
                or not 1 <= component["best_n"] <= len(keys)
            ):
                raise ValueError("Best N must be within the component's assessment count.")
            weight += w
        if weight != 100:
            raise ValueError("Contribution percentages must total exactly 100.")
    except (KeyError, TypeError, ValueError) as error:
        return [{"message": str(error)}]
    return []


def calculate_score(definition, marks):
    errors = validate_rule(definition)
    if errors:
        raise ValueError(errors[0]["message"])
    contributions, pending = {}, []
    final = Decimal(0)
    for component in definition["components"]:
        weight = decimal(component["weight_percent"])
        if not weight:
            continue
        values, maxima = [], []
        missing = []
        for key in component["assessment_keys"]:
            mark = marks.get(key, {"status": "missing"})
            maximum = decimal(definition["assessments"][key])
            if mark["status"] == "missing":
                missing.append(key)
                continue
            if mark["status"] not in ("scored", "absent"):
                raise ValueError("Unknown mark status.")
            value = Decimal(0) if mark["status"] == "absent" else decimal(mark["value"])
            if not 0 <= value <= maximum:
                raise ValueError(f"{key} is outside its configured maximum.")
            values.append(value)
            maxima.append(maximum)
        if missing:
            pending.extend(missing)
            continue
        ratios = [v / m for v, m in zip(values, maxima, strict=True)]
        method = component["aggregation"]
        if method == "sum_ratio":
            ratio = sum(values) / sum(maxima)
        elif method == "best_n":
            chosen = sorted(ratios, reverse=True)[: component["best_n"]]
            ratio = sum(chosen) / len(chosen)
        else:
            ratio = sum(ratios) / len(ratios)
        contribution = ratio * weight / 100 * decimal(definition["final_maximum"])
        contributions[component["id"]] = contribution
        final += contribution
    quantum, mode = ROUNDING[definition["rounding"]]
    return {
        "status": "pending" if pending else "complete",
        "pending_keys": pending,
        "contributions": contributions,
        "unrounded": None if pending else final,
        "rounded": None if pending else final.quantize(Decimal(quantum), rounding=mode),
    }

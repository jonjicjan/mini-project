from core.errors import DomainError
from registers.entries import clean_save, mutate_register

from .calculations import KEYS, decimal, validate_rule
from .models import Mark, RegisterMarkingRule


def save_rule(actor, register_id, *, definition, expected_revision, request_id):
    def change(register):
        errors = validate_rule(definition)
        if errors:
            raise DomainError(errors[0]["message"])
        for mark in Mark.objects.filter(enrollment__register=register, status="scored"):
            if mark.value > decimal(definition["assessments"][mark.assessment_key]):
                raise DomainError(
                    f"Correct {mark.enrollment.usn} {mark.assessment_key} before reducing its maximum."
                )
        RegisterMarkingRule.objects.update_or_create(
            register=register, defaults={"definition": definition}
        )
        return {"definition": definition}

    return mutate_register(
        actor,
        register_id,
        action="save_marking_rule",
        values=definition,
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )


def save_marks(actor, register_id, *, rows, expected_revision, request_id):
    def change(register):
        if not hasattr(register, "marking_rule"):
            raise DomainError("Save this register's assessment rules before entering marks.")
        rule = register.marking_rule.definition
        if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
            raise DomainError("Enter between 1 and 2,000 mark rows.")
        seen, changes = set(), []
        for row in rows:
            usn = str(row.get("usn", "")).strip().upper()
            student = register.students.filter(usn=usn).first()
            if not student or usn in seen:
                raise DomainError(
                    "Each marks row must identify a different student in this register."
                )
            seen.add(usn)
            if set(row) - {"usn", *KEYS}:
                raise DomainError("Unknown marks columns.")
            for key in KEYS:
                raw = str(row.get(key, "")).strip().upper()
                if not raw:
                    continue  # A blank pasted cell preserves existing data.
                value, status = None, "missing"
                if raw == "AB":
                    status = "absent"
                elif raw != "CLEAR":
                    try:
                        value = decimal(raw)
                    except ValueError as error:
                        raise DomainError(str(error)) from error
                    if not 0 <= value <= decimal(rule["assessments"][key]):
                        raise DomainError(
                            f"{usn}: {key} must be between zero and {rule['assessments'][key]}."
                        )
                    status = "scored"
                mark, _ = Mark.objects.get_or_create(enrollment=student, assessment_key=key)
                mark.status, mark.value, mark.revision = status, value, mark.revision + 1
                clean_save(mark)
                changes.append({"usn": usn, "key": key, "status": status, "value": value})
        return {"changes": changes}

    return mutate_register(
        actor,
        register_id,
        action="save_marks",
        values={"rows": rows},
        change=change,
        expected_revision=expected_revision,
        request_id=request_id,
    )

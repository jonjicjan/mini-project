from decimal import Decimal


def summarise_statuses(statuses):
    attended = eligible = 0
    provisional = False
    sequence = []
    for status in statuses:
        if status not in ("present", "absent", "unmarked", "not_applicable"):
            raise ValueError("Unknown attendance status.")
        if status == "not_applicable":
            sequence.append("-")
            continue
        eligible += 1
        if status == "present":
            attended += 1
            sequence.append(str(attended))
        elif status == "absent":
            sequence.append("A")
        else:
            provisional = True
            sequence.append("")
    return {
        "attended": attended,
        "eligible": eligible,
        "percentage": Decimal(attended) * 100 / eligible if eligible else None,
        "sequence": sequence,
        "provisional": provisional,
    }

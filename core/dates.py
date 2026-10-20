from datetime import datetime


def parse_date(value):
    value = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            result = datetime.strptime(value, pattern).date()
            if result.strftime(pattern) == value:
                return result
        except ValueError:
            pass
    raise ValueError("Use YYYY-MM-DD or DD/MM/YYYY with a four-digit year.")

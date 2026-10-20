class DomainError(Exception):
    def __init__(self, message, *, code="invalid", status=422, field_errors=None, **details):
        super().__init__(message)
        self.status = status
        self.body = {
            "code": code,
            "message": message,
            "field_errors": field_errors or {},
            **details,
        }


def conflict(message, **details):
    return DomainError(message, code="conflict", status=409, **details)

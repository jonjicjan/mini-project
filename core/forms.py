import uuid

from django import forms


class MutationForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    request_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, revision=0, **kwargs):
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("expected_revision", revision)
        initial.setdefault("request_id", uuid.uuid4())
        super().__init__(*args, **kwargs)

    def operation(self):
        return {key: self.cleaned_data[key] for key in ("expected_revision", "request_id")}

    def show_domain_error(self, error):
        self.add_error(None, str(error))
        for field, errors in error.body.get("field_errors", {}).items():
            if not isinstance(errors, list):
                errors = [errors]
            for message in errors:
                self.add_error(field if field in self.fields else None, message)

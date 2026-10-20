from django import forms

from core.forms import MutationForm

from .models import Register


class RegisterForm(MutationForm, forms.ModelForm):
    class Meta:
        model = Register
        fields = [
            "subject_name",
            "subject_code",
            "academic_year",
            "faculty_name",
            "branch",
            "semester",
            "section",
            "term_start",
            "term_end",
        ]
        labels = {
            "branch": "Department / branch",
            "subject_name": "Subject name",
            "subject_code": "Subject code",
            "term_start": "Term starts",
            "term_end": "Term ends",
        }
        widgets = {
            "term_start": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "term_end": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def values(self):
        return {key: self.cleaned_data[key] for key in self.Meta.fields}


class ArchiveForm(MutationForm):
    archived = forms.TypedChoiceField(
        choices=[("yes", "Archive"), ("no", "Restore")],
        coerce=lambda value: value == "yes",
        widget=forms.HiddenInput,
    )

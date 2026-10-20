from django import forms

from assessments.calculations import KEYS, ROUNDING, default_rule
from core.forms import MutationForm
from registers.models import Enrollment, LessonPlanRow
from scheduling.models import Holiday, Session, TimetableEntry


class EntryForm(MutationForm, forms.ModelForm):
    def __init__(self, *args, register, **kwargs):
        self.register = register
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                field.input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
                field.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            elif isinstance(field, forms.TimeField):
                field.widget = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")

    def values(self):
        values = {key: self.cleaned_data[key] for key in self.Meta.fields}
        if self.instance.pk:
            # UUID defaults exist even on unsaved instances.
            if not self.instance._state.adding:
                values["id"] = str(self.instance.pk)
        return values


class StudentForm(EntryForm):
    class Meta:
        model = Enrollment
        fields = ["usn", "name", "serial_number", "eligible_from", "eligible_to"]
        labels = {
            "eligible_from": "Attendance eligibility starts",
            "eligible_to": "Eligibility ends (optional)",
        }


class LessonForm(EntryForm):
    class Meta:
        model = LessonPlanRow
        fields = [
            "original_number",
            "topic",
            "original_date",
            "original_period",
            "reported_execution_date",
            "remarks",
        ]
        widgets = {
            "topic": forms.Textarea(attrs={"rows": 3}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }


class SlotForm(EntryForm):
    class Meta:
        model = TimetableEntry
        fields = ["weekday", "period", "start_time", "end_time", "effective_from", "effective_to"]


class SessionForm(EntryForm):
    replacement = forms.ModelChoiceField(
        queryset=Session.objects.none(),
        required=False,
        label="Replace this unrecorded class (optional)",
        help_text="For a test, select the class it replaces. Leave empty for an extra event.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lesson"].queryset = self.register.lessons.all()
        self.fields["replacement"].queryset = self.register.sessions.filter(
            status="planned", attendance__isnull=True
        )

    def values(self):
        return super().values() | {
            "replacement": self.cleaned_data["replacement"].pk
            if self.cleaned_data["replacement"]
            else None
        }

    class Meta:
        model = Session
        fields = [
            "lesson",
            "kind",
            "test_number",
            "scheduled_date",
            "actual_date",
            "period",
            "start_time",
            "end_time",
            "status",
            "exception_reason",
        ]
        labels = {
            "actual_date": "Actual date (historical correction)",
            "exception_reason": "Correction / exception reason",
        }


class HolidayForm(EntryForm):
    class Meta:
        model = Holiday
        fields = ["start_date", "end_date", "reason"]


class PasteForm(MutationForm):
    text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 7}), max_length=500000, label="Paste rows"
    )
    delimiter = forms.ChoiceField(
        choices=[("tab", "Tabs (Excel / Word table)"), ("comma", "Comma-separated CSV")]
    )
    columns = forms.CharField(
        label="Column order",
        help_text="Comma-separated field names in the same order as your pasted columns.",
    )


class RulesForm(MutationForm):
    final_maximum = forms.DecimalField(min_value=1, max_value=1000000, initial=50)
    assignment_weight = forms.DecimalField(
        min_value=0, max_value=100, initial=40, label="Assignments contribution (%)"
    )
    test_weight = forms.DecimalField(
        min_value=0, max_value=100, initial=60, label="Tests contribution (%)"
    )
    assignment_method = forms.ChoiceField(
        choices=[
            ("mean_normalised", "Average percentages"),
            ("sum_ratio", "Total earned / total possible"),
            ("best_n", "Best N percentages"),
        ]
    )
    assignment_best_n = forms.IntegerField(min_value=1, max_value=3, initial=2)
    test_method = forms.ChoiceField(
        choices=[
            ("mean_normalised", "Average percentages"),
            ("sum_ratio", "Total earned / total possible"),
            ("best_n", "Best N percentages"),
        ]
    )
    test_best_n = forms.IntegerField(min_value=1, max_value=3, initial=2)
    rounding = forms.ChoiceField(
        choices=[(key, key.replace("_", " ").capitalize()) for key in ROUNDING]
    )

    def __init__(self, *args, definition=None, **kwargs):
        definition = definition or default_rule()
        initial = kwargs.setdefault("initial", {})
        initial.update(final_maximum=definition["final_maximum"], rounding=definition["rounding"])
        for prefix, component in zip(["assignment", "test"], definition["components"], strict=True):
            initial.update(
                {
                    f"{prefix}_weight": component["weight_percent"],
                    f"{prefix}_method": component["aggregation"],
                    f"{prefix}_best_n": component.get("best_n", 2),
                }
            )
        initial.update({f"maximum_{key}": definition["assessments"][key] for key in KEYS})
        super().__init__(*args, **kwargs)
        for key in KEYS:
            self.fields[f"maximum_{key}"] = forms.DecimalField(
                min_value=1, max_value=1000000, label=f"{key} maximum"
            )

    def definition(self):
        data = self.cleaned_data
        result = default_rule()
        result.update(final_maximum=str(data["final_maximum"]), rounding=data["rounding"])
        result["assessments"] = {key: str(data[f"maximum_{key}"]) for key in KEYS}
        for prefix, component in zip(["assignment", "test"], result["components"], strict=True):
            component.update(
                weight_percent=str(data[f"{prefix}_weight"]),
                aggregation=data[f"{prefix}_method"],
                best_n=data[f"{prefix}_best_n"],
            )
        return result


class MarksForm(MutationForm):
    usn = forms.ChoiceField(label="Student")

    def __init__(self, *args, register, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usn"].choices = [
            (s.usn, f"{s.usn} · {s.name}") for s in register.students.all()
        ]
        for key in KEYS:
            self.fields[key] = forms.CharField(
                required=False,
                max_length=20,
                help_text="Number, AB (absent), or CLEAR. Blank keeps the saved mark.",
            )


class ThroughForm(MutationForm):
    through = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    draft = forms.BooleanField(
        required=False, initial=True, label="Draft export (allows incomplete attendance / marks)"
    )

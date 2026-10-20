from django import forms

from core.forms import MutationForm


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username"})
    )
    password = forms.CharField(
        strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )


class FacultyForm(MutationForm):
    username = forms.CharField(max_length=150, help_text="Use letters, numbers and @ . + - _")
    display_name = forms.CharField(max_length=150, label="Faculty name")
    temporary_password = forms.CharField(
        strip=False,
        min_length=12,
        label="Initial password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 12 characters. Give this password to the faculty member directly.",
    )


class ResetForm(MutationForm):
    password = forms.CharField(
        strip=False,
        min_length=12,
        label="New password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

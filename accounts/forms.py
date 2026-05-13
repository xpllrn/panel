from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import aadhar_validator, pan_validator, phone_validator


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))


class SetupAdminProfileForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    mobile_primary = forms.CharField(max_length=15, validators=[phone_validator])
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data


class SetupKYCForm(forms.Form):
    aadhaar_number = forms.CharField(max_length=12)
    pan_number = forms.CharField(max_length=10)

    def clean_aadhaar_number(self):
        aadhaar_number = "".join((self.cleaned_data.get("aadhaar_number") or "").split())
        aadhar_validator(aadhaar_number)
        return aadhaar_number

    def clean_pan_number(self):
        pan_number = (self.cleaned_data.get("pan_number") or "").strip().upper()
        pan_validator(pan_number)
        return pan_number


class SetupSocietyForm(forms.Form):
    society_name = forms.CharField(max_length=255)
    society_logo = forms.ImageField(required=False)


class SetupPenaltyForm(forms.Form):
    late_payment_penalty_per_day = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0)

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"})
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Password"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm Password"})


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))


class UserProfileForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
    )

    class Meta:
        model = User
        fields = ["email", "mobile_primary"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "mobile_primary": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Populate name field with display_name
            self.fields["name"].initial = self.instance.display_name

    def save(self, commit=True):
        user = super().save(commit=False)
        # Set first_name and last_name from name field
        name = self.cleaned_data.get("name", "").strip()
        if name:
            from accounts.utils import split_full_name

            user.first_name, user.last_name = split_full_name(name)
        if commit:
            user.save()
        return user


class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["preferred_comm_mode", "dnd_enabled"]
        widgets = {
            "preferred_comm_mode": forms.Select(attrs={"class": "form-control"}),
            "dnd_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

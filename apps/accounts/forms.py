"""
Authentication forms for the ESOP platform.
"""

from django import forms
from django.contrib.auth import authenticate


class SecureLoginForm(forms.Form):
    """
    Login form with CSRF protection (automatic in Django).
    Does NOT reveal whether the username or password was wrong.
    """

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Username",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Invalid credentials. Please try again.",
                    code="invalid_login",
                )

        return cleaned_data

    def get_user(self):
        return self.user_cache


class MFAVerifyForm(forms.Form):
    """
    TOTP verification form for MFA step.
    """

    token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "6-digit code",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autofocus": True,
            }
        ),
        help_text="Enter the 6-digit code from your authenticator app.",
    )


"""
Month-end run forms with validation.
"""

import uuid
from datetime import date

from django import forms

from .models import MonthEndRun


class MonthEndRunForm(forms.ModelForm):
    """Form for creating/editing a month-end run."""

    # Title is optional - auto-generated in clean() if not provided
    title = forms.CharField(max_length=255, required=False)

    class Meta:
        model = MonthEndRun
        fields = [
            "title",
            "description",
            "period_year",
            "period_month",
            "idempotency_key",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "idempotency_key": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-generate idempotency key for new runs
        if self.instance._state.adding:
            self.initial["idempotency_key"] = f"ME-{uuid.uuid4().hex[:12].upper()}"

        # Set default period to current month
        if not self.initial.get("period_year"):
            today = date.today()
            self.initial["period_year"] = today.year
            self.initial["period_month"] = today.month

    def clean_period_month(self):
        month = self.cleaned_data.get("period_month")
        if month and (month < 1 or month > 12):
            raise forms.ValidationError("Month must be between 1 and 12.")
        return month

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("period_year")
        month = cleaned_data.get("period_month")

        if year and month:
            # Auto-generate title if not provided
            if not cleaned_data.get("title"):
                import calendar
                cleaned_data["title"] = f"{calendar.month_name[month]} {year} Month-End"

        return cleaned_data


class ProcessRunForm(forms.Form):
    """Form for processing a month-end run with required parameters."""

    share_price = forms.DecimalField(
        max_digits=12,
        decimal_places=4,
        min_value=0.0001,
        help_text="Current share price in ZAR.",
    )
    tax_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=0,
        max_value=1,
        initial="0.3500",
        help_text="Tax rate for share sales (e.g. 0.35 = 35%).",
    )


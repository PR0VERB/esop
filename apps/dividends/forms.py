"""
Dividend run forms with validation.

Security notes:
- Company and created_by are set server-side (never from client input).
- Idempotency key generated server-side if not provided.
- record_date must be before payment_date.
- Only DRAFT runs can be edited.
"""

import uuid

from django import forms

from .models import DividendRun


class DividendRunForm(forms.ModelForm):
    """Create / edit form for dividend runs (DRAFT only)."""

    class Meta:
        model = DividendRun
        fields = [
            "title",
            "description",
            "total_amount",
            "dividend_per_share",
            "dwt_rate",
            "record_date",
            "payment_date",
            "declaration_date",
            "idempotency_key",
        ]
        widgets = {
            "record_date": forms.DateInput(attrs={"type": "date"}),
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "declaration_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-generate idempotency key if creating (UUID pk is always set via default)
        if self.instance._state.adding:
            self.fields["idempotency_key"].initial = str(uuid.uuid4())
        self.fields["idempotency_key"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        record_date = cleaned.get("record_date")
        payment_date = cleaned.get("payment_date")

        if record_date and payment_date and record_date >= payment_date:
            raise forms.ValidationError(
                "Record date must be before payment date."
            )
        return cleaned


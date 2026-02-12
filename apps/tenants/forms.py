"""
Company creation and editing forms.

The jse_ticker, jse_isin, and sector fields are optional
and can be auto-populated from the JSE company search.
"""

from django import forms

from .models import Company


class CompanyCreateForm(forms.ModelForm):
    """
    Form for creating a new Company tenant.
    Fields can be auto-populated from JSE search selection.
    """

    class Meta:
        model = Company
        fields = [
            "name",
            "registration_number",
            "tax_number",
            "jse_ticker",
            "jse_isin",
            "sector",
            "scheme_name",
            "trust_name",
            "trust_bank_account",
        ]
        widgets = {
            "trust_bank_account": forms.TextInput(
                attrs={"placeholder": "Trust bank account number"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in [
            "tax_number", "jse_ticker", "jse_isin", "sector",
            "scheme_name", "trust_name", "trust_bank_account",
        ]:
            self.fields[field_name].required = False

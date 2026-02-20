"""
Beneficiary forms with field-level validation and encryption.

Security notes:
- SA ID number is validated for format (13 digits, Luhn check).
- Bank account number encrypted before save.
- Company is set server-side (never from client).
"""

import re

from django import forms

from .models import BankAccountType, Beneficiary, BeneficiaryStatus


class BeneficiaryForm(forms.ModelForm):
    """
    Create / update form for beneficiaries.
    Encrypted fields (id_number, account_number) are handled as plain-text
    inputs and encrypted on save.
    """

    # Virtual fields – plain text for the form, encrypted on save
    id_number = forms.CharField(
        max_length=13,
        required=False,
        help_text="South African ID number (13 digits).",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 8501015009087"}),
    )
    account_number = forms.CharField(
        max_length=20,
        required=False,
        help_text="Bank account number.",
        widget=forms.TextInput(attrs={"placeholder": "Account number"}),
    )

    class Meta:
        model = Beneficiary
        fields = [
            "employee_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "email",
            "phone",
            "tax_number",
            "bank_name",
            "account_type",
            "branch_code",
            "total_shares",
            "vested_shares",
            "unvested_shares",
            "status",
            "employment_date",
            "scheme_join_date",
            "termination_date",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "employment_date": forms.DateInput(attrs={"type": "date"}),
            "scheme_join_date": forms.DateInput(attrs={"type": "date"}),
            "termination_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        """Pre-populate decrypted values when editing."""
        self.company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["id_number"].initial = self.instance.id_number
            self.fields["account_number"].initial = self.instance.account_number

    # -------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------
    def clean_employee_number(self):
        """Enforce unique (company, employee_number) at form level."""
        emp_no = self.cleaned_data.get("employee_number", "").strip()
        if emp_no and self.company:
            qs = Beneficiary.objects.filter(
                company=self.company, employee_number=emp_no
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"A beneficiary with employee number '{emp_no}' already exists "
                    f"for this company."
                )
        return emp_no

    def clean_id_number(self):
        """Validate SA ID number format (13 digits, Luhn check)."""
        value = self.cleaned_data.get("id_number", "").strip()
        if not value:
            return value
        if not re.match(r"^[0-9]{13}$", value):
            raise forms.ValidationError("SA ID number must be exactly 13 digits.")
        if not self._luhn_check(value):
            raise forms.ValidationError("Invalid SA ID number (checksum failed).")
        return value

    def clean_account_number(self):
        """Bank account numbers: digits only, 6–20 chars."""
        value = self.cleaned_data.get("account_number", "").strip()
        if not value:
            return value
        if not re.match(r"^[0-9]{6,20}$", value):
            raise forms.ValidationError(
                "Account number must be 6–20 digits."
            )
        return value

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get("total_shares", 0) or 0
        vested = cleaned.get("vested_shares", 0) or 0
        unvested = cleaned.get("unvested_shares", 0) or 0

        if vested + unvested != total:
            raise forms.ValidationError(
                "Vested shares + unvested shares must equal total shares."
            )
        return cleaned

    def save(self, commit=True):
        """Encrypt sensitive fields before saving."""
        instance = super().save(commit=False)
        id_number = self.cleaned_data.get("id_number", "")
        account_number = self.cleaned_data.get("account_number", "")

        # Use the property setters which handle encryption
        instance.id_number = id_number
        instance.account_number = account_number

        if commit:
            instance.save()
        return instance

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------
    @staticmethod
    def _luhn_check(id_number: str) -> bool:
        """Luhn algorithm for SA ID numbers."""
        digits = [int(d) for d in id_number]
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        return checksum % 10 == 0


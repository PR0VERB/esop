"""
API Serializers for ESOP models.

Security notes:
- Encrypted fields (id_number, bank account) are NEVER exposed in API.
- Properties are used instead of encrypted storage fields.
- Company ID is read-only (set from authenticated user's context).
- Created_by is read-only (set from authenticated user).
"""

from rest_framework import serializers

from apps.beneficiaries.models import Beneficiary, BeneficiaryStatus, LeaverType
from apps.integrations.models import JSECompany
from apps.dividends.models import DividendRun, DividendAllocation, RunStatus, AllocationStatus
from apps.month_end.models import (
    MonthEndRun, MonthEndRunStatus,
    VestingEvent, VestingEventType, VestingEventStatus,
    TaxDirective, TaxDirectiveStatus,
)


# -----------------------------------------------------------------------------
# Beneficiary Serializers
# -----------------------------------------------------------------------------

class BeneficiaryListSerializer(serializers.ModelSerializer):
    """Minimal beneficiary info for list views."""
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Beneficiary
        fields = [
            "id", "employee_number", "first_name", "last_name", "full_name",
            "email", "status", "status_display", "total_shares", "vested_shares",
            "unvested_shares", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class BeneficiaryDetailSerializer(serializers.ModelSerializer):
    """
    Full beneficiary details for create/update.
    
    Note: id_number and account_number are handled via properties.
    Encrypted storage fields are never exposed.
    """
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    leaver_type_display = serializers.CharField(source="get_leaver_type_display", read_only=True)
    
    # Use properties for sensitive data (masked in responses)
    id_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    account_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = Beneficiary
        fields = [
            "id", "employee_number", "first_name", "last_name", "email", "phone",
            "date_of_birth", "tax_number", "id_number",
            "bank_name", "account_number", "account_type", "branch_code",
            "total_shares", "vested_shares", "unvested_shares",
            "status", "status_display", "leaver_type", "leaver_type_display",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status_display", "leaver_type_display"]
    
    def create(self, validated_data):
        # Handle encrypted fields via properties
        id_number = validated_data.pop("id_number", None)
        account_number = validated_data.pop("account_number", None)
        
        instance = super().create(validated_data)
        
        if id_number:
            instance.id_number = id_number
        if account_number:
            instance.account_number = account_number
        
        if id_number or account_number:
            instance.save()
        
        return instance
    
    def update(self, instance, validated_data):
        # Handle encrypted fields via properties
        id_number = validated_data.pop("id_number", None)
        account_number = validated_data.pop("account_number", None)
        
        instance = super().update(instance, validated_data)
        
        if id_number is not None:
            instance.id_number = id_number
        if account_number is not None:
            instance.account_number = account_number
        
        if id_number is not None or account_number is not None:
            instance.save()
        
        return instance


# -----------------------------------------------------------------------------
# Dividend Serializers
# -----------------------------------------------------------------------------

class DividendAllocationSerializer(serializers.ModelSerializer):
    """Dividend allocation within a run."""
    
    beneficiary_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = DividendAllocation
        fields = [
            "id", "beneficiary", "beneficiary_name", "shares_at_record_date",
            "gross_amount", "tax_amount", "net_amount",
            "status", "status_display", "payment_reference", "created_at",
        ]
        read_only_fields = fields  # Allocations are created by processing, not API
    
    def get_beneficiary_name(self, obj):
        return f"{obj.beneficiary.first_name} {obj.beneficiary.last_name}"


class DividendRunListSerializer(serializers.ModelSerializer):
    """Minimal dividend run info for list views."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DividendRun
        fields = [
            "id", "title", "total_amount", "dividend_per_share",
            "record_date", "payment_date", "status", "status_display",
            "allocation_count", "total_net", "created_at",
        ]
        read_only_fields = ["id", "allocation_count", "total_net", "created_at"]


class DividendRunDetailSerializer(serializers.ModelSerializer):
    """Full dividend run details with nested allocations."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    allocations = DividendAllocationSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = DividendRun
        fields = [
            "id", "title", "description", "total_amount", "dividend_per_share",
            "dwt_rate", "record_date", "ldt_date", "payment_date", "declaration_date",
            "status", "status_display", "idempotency_key",
            "created_by", "created_by_username", "approved_by", "approved_by_username",
            "approved_at", "completed_at", "failure_reason",
            "total_gross", "total_tax", "total_net", "allocation_count",
            "allocations", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "created_by", "approved_by", "approved_at",
            "completed_at", "total_gross", "total_tax", "total_net",
            "allocation_count", "created_at", "updated_at",
        ]


class DividendRunCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating dividend runs."""

    class Meta:
        model = DividendRun
        fields = [
            "title", "description", "total_amount", "dividend_per_share",
            "dwt_rate", "record_date", "ldt_date", "payment_date", "declaration_date",
            "idempotency_key",
        ]


# -----------------------------------------------------------------------------
# Month-End Serializers
# -----------------------------------------------------------------------------

class VestingEventSerializer(serializers.ModelSerializer):
    """Vesting event within a month-end run."""

    beneficiary_name = serializers.SerializerMethodField()
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = VestingEvent
        fields = [
            "id", "beneficiary", "beneficiary_name", "event_type", "event_type_display",
            "event_date", "shares_affected", "shares_before", "shares_after",
            "share_price", "gross_proceeds", "tax_amount", "net_proceeds",
            "status", "status_display", "created_at",
        ]
        read_only_fields = fields  # Events are created by processing, not API

    def get_beneficiary_name(self, obj):
        return f"{obj.beneficiary.first_name} {obj.beneficiary.last_name}"


class TaxDirectiveSerializer(serializers.ModelSerializer):
    """Tax directive info."""

    beneficiary_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TaxDirective
        fields = [
            "id", "beneficiary", "beneficiary_name", "gross_income",
            "requested_rate", "approved_rate", "directive_number",
            "requested_at", "received_at", "valid_until",
            "status", "status_display", "created_at",
        ]
        read_only_fields = fields  # Directives are created by processing, not API

    def get_beneficiary_name(self, obj):
        return f"{obj.beneficiary.first_name} {obj.beneficiary.last_name}"


class MonthEndRunListSerializer(serializers.ModelSerializer):
    """Minimal month-end run info for list views."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    period_display = serializers.CharField(read_only=True)

    class Meta:
        model = MonthEndRun
        fields = [
            "id", "title", "period_year", "period_month", "period_display",
            "status", "status_display", "vesting_event_count", "termination_count",
            "total_net_proceeds", "created_at",
        ]
        read_only_fields = ["id", "vesting_event_count", "termination_count",
                           "total_net_proceeds", "created_at"]


class MonthEndRunDetailSerializer(serializers.ModelSerializer):
    """Full month-end run details with nested events."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    period_display = serializers.CharField(read_only=True)
    vesting_events = VestingEventSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_username = serializers.CharField(
        source="approved_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = MonthEndRun
        fields = [
            "id", "title", "description", "period_year", "period_month", "period_display",
            "status", "status_display", "idempotency_key",
            "created_by", "created_by_username", "approved_by", "approved_by_username",
            "approved_at", "completed_at", "failure_reason",
            "total_shares_vested", "total_shares_sold", "total_gross_proceeds",
            "total_tax", "total_net_proceeds", "vesting_event_count", "termination_count",
            "vesting_events", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "created_by", "approved_by", "approved_at",
            "completed_at", "total_shares_vested", "total_shares_sold",
            "total_gross_proceeds", "total_tax", "total_net_proceeds",
            "vesting_event_count", "termination_count", "created_at", "updated_at",
        ]


class MonthEndRunCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating month-end runs."""

    class Meta:
        model = MonthEndRun
        fields = [
            "title", "description", "period_year", "period_month",
            "idempotency_key",
        ]


# -----------------------------------------------------------------------------
# JSE Company Serializers
# -----------------------------------------------------------------------------

class JSECompanySearchSerializer(serializers.ModelSerializer):
    """Read-only serializer for JSE company search results."""

    yahoo_ticker = serializers.CharField(read_only=True)

    class Meta:
        model = JSECompany
        fields = [
            "id", "ticker", "company_name", "isin", "sector",
            "market_cap_category", "registration_number",
            "share_price", "market_cap", "last_enriched_at",
            "yahoo_ticker",
        ]
        read_only_fields = fields


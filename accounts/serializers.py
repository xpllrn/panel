from rest_framework import serializers

from accounts.models import (
    AuditLog,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    Loan,
    LoanRepayment,
    MemberAccount,
    Notification,
    Receipt,
    User,
)

# ========================================
# User / Member Serializers
# ========================================


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "member_id",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "member_type",
            "status",
            "date_of_joining",
            "mobile_primary",
            "is_staff",
            "is_active",
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail views."""

    display_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "member_id",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "member_type",
            "status",
            "date_of_joining",
            "exit_date",
            "date_of_birth",
            "age",
            "gender",
            "marital_status",
            "occupation",
            "mobile_primary",
            "mobile_alternate",
            "preferred_comm_mode",
            "current_address_line1",
            "current_address_line2",
            "current_city",
            "current_district",
            "current_state",
            "current_pincode",
            "permanent_same_as_current",
            "permanent_address_line1",
            "permanent_city",
            "permanent_state",
            "permanent_pincode",
            "kyc_status",
            "aadhar_number",
            "pan_number",
            "voter_id",
            "eligible_for_accounts",
            "eligible_for_loans",
            "eligible_for_dividend",
            "risk_category",
            "share_capital_amount",
            "number_of_shares",
            "face_value_per_share",
            "dividend_payable_balance",
            "last_dividend_paid_date",
            "nominee_name",
            "nominee_relationship",
            "nominee_contact",
            "total_deposit_balance",
            "total_loan_outstanding",
            "portal_access_enabled",
            "is_staff",
            "is_active",
        ]
        read_only_fields = ["id", "username", "total_deposit_balance", "total_loan_outstanding"]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new members."""

    full_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "member_type",
            "date_of_birth",
            "gender",
            "mobile_primary",
            "occupation",
            "current_address_line1",
            "current_city",
            "current_state",
            "current_pincode",
            "aadhar_number",
            "pan_number",
            "password",
        ]

    def create(self, validated_data):
        from accounts.utils import split_full_name

        full_name = validated_data.pop("full_name", "")
        password = validated_data.pop("password", None)
        first_name, last_name = split_full_name(full_name)

        # Generate member ID
        from datetime import date

        year = date.today().year
        last_user = User.objects.filter(member_id__startswith=f"MEM-{year}").order_by("-member_id").first()
        if last_user and last_user.member_id:
            try:
                last_seq = int(last_user.member_id.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        member_id = f"MEM-{year}-{next_seq:04d}"

        # Generate username
        username = member_id.lower().replace("-", "")

        user = User(
            username=username,
            member_id=member_id,
            first_name=first_name,
            last_name=last_name,
            role="member",
            date_of_joining=date.today(),
            **validated_data,
        )

        if password:
            user.set_password(password)
        else:
            generated = user.generate_password_from_dob()
            if generated:
                user.set_password(generated)
            else:
                user.set_password("changeme123")

        user.save()
        return user


class MemberProfileSerializer(serializers.ModelSerializer):
    """Serializer for member's own profile (limited fields)."""

    display_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "member_id",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "email_verified",
            "member_type",
            "status",
            "date_of_joining",
            "date_of_birth",
            "age",
            "gender",
            "mobile_primary",
            "current_city",
            "current_state",
            "share_capital_amount",
            "number_of_shares",
            "dividend_payable_balance",
        ]
        read_only_fields = fields


# ========================================
# Account Serializers
# ========================================


class MemberAccountSerializer(serializers.ModelSerializer):
    """Full account serializer."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    maturity_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = MemberAccount
        fields = [
            "id",
            "user",
            "user_display",
            "account_number",
            "account_type",
            "account_type_display",
            "status",
            "status_display",
            "balance",
            "interest_rate",
            "principal_amount",
            "accrued_interest",
            "rd_monthly_amount",
            "rd_installments_paid",
            "rd_total_installments",
            "opening_date",
            "maturity_date",
            "closure_date",
            "tenure_months",
            "nominee_name",
            "nominee_relationship",
            "maturity_amount",
            "created_at",
        ]
        read_only_fields = ["id", "account_number", "balance", "accrued_interest", "created_at"]


class MemberAccountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating accounts."""

    class Meta:
        model = MemberAccount
        fields = [
            "user",
            "account_type",
            "interest_rate",
            "principal_amount",
            "rd_monthly_amount",
            "rd_total_installments",
            "opening_date",
            "maturity_date",
            "tenure_months",
            "nominee_name",
            "nominee_relationship",
        ]


# ========================================
# Receipt / Transaction Serializers
# ========================================


class ReceiptSerializer(serializers.ModelSerializer):
    """Full receipt serializer."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    account_number = serializers.CharField(source="member_account.account_number", read_only=True)
    transaction_type_display = serializers.CharField(source="get_transaction_type_display", read_only=True)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "receipt_number",
            "user",
            "user_display",
            "member_account",
            "account_number",
            "transaction_type",
            "transaction_type_display",
            "amount",
            "description",
            "payment_mode",
            "reference_number",
            "balance_after",
            "created_by",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "receipt_number", "balance_after", "created_by", "created_at"]


class ReceiptCreateSerializer(serializers.Serializer):
    """Serializer for creating receipts (deposits/withdrawals)."""

    member_account = serializers.IntegerField()
    transaction_type = serializers.ChoiceField(choices=Receipt.TRANSACTION_TYPE_CHOICES)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_mode = serializers.ChoiceField(choices=Receipt.PAYMENT_MODE_CHOICES, default="cash")
    description = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)


# ========================================
# Loan Serializers
# ========================================


class LoanListSerializer(serializers.ModelSerializer):
    """Lightweight loan serializer for list views."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    loan_type_display = serializers.CharField(source="get_loan_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)
    is_npa = serializers.BooleanField(read_only=True)

    class Meta:
        model = Loan
        fields = [
            "id",
            "loan_number",
            "user",
            "user_display",
            "loan_type",
            "loan_type_display",
            "status",
            "status_display",
            "principal_amount",
            "interest_rate",
            "tenure_months",
            "emi_amount",
            "outstanding_balance",
            "overdue_amount",
            "emis_paid",
            "total_emis",
            "completion_percentage",
            "is_npa",
            "application_date",
            "disbursement_date",
        ]


class LoanDetailSerializer(serializers.ModelSerializer):
    """Full loan detail serializer."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    loan_type_display = serializers.CharField(source="get_loan_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)
    is_npa = serializers.BooleanField(read_only=True)
    npa_category = serializers.CharField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)

    class Meta:
        model = Loan
        fields = [
            "id",
            "loan_number",
            "user",
            "user_display",
            "loan_type",
            "loan_type_display",
            "status",
            "status_display",
            "principal_amount",
            "interest_rate",
            "interest_type",
            "tenure_months",
            "emi_amount",
            "total_payable",
            "total_paid",
            "outstanding_balance",
            "overdue_amount",
            "processing_fee",
            "application_date",
            "approval_date",
            "disbursement_date",
            "first_emi_date",
            "last_emi_date",
            "closure_date",
            "total_emis",
            "emis_paid",
            "emis_overdue",
            "completion_percentage",
            "guarantor_name",
            "guarantor_member_id",
            "guarantor_contact",
            "collateral_type",
            "collateral_value",
            "collateral_description",
            "disbursement_account",
            "purpose",
            "remarks",
            "approved_by",
            "created_by",
            "is_npa",
            "npa_category",
            "npa_date",
            "days_overdue",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "loan_number",
            "total_payable",
            "total_paid",
            "outstanding_balance",
            "overdue_amount",
            "emis_paid",
            "emis_overdue",
            "approved_by",
            "created_by",
            "created_at",
        ]


class LoanCreateSerializer(serializers.Serializer):
    """Serializer for creating loans."""

    user = serializers.IntegerField()
    loan_type = serializers.ChoiceField(choices=Loan.LOAN_TYPE_CHOICES)
    principal_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    interest_type = serializers.ChoiceField(choices=Loan.INTEREST_TYPE_CHOICES, default="reducing")
    tenure_months = serializers.IntegerField()
    processing_fee = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    disbursement_account = serializers.IntegerField(required=False)
    purpose = serializers.CharField(required=False, allow_blank=True)
    guarantor_name = serializers.CharField(required=False, allow_blank=True)
    guarantor_member_id = serializers.CharField(required=False, allow_blank=True)
    guarantor_contact = serializers.CharField(required=False, allow_blank=True)
    collateral_type = serializers.CharField(required=False, allow_blank=True)
    collateral_value = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)


class LoanRepaymentSerializer(serializers.ModelSerializer):
    """Loan repayment / EMI serializer."""

    class Meta:
        model = LoanRepayment
        fields = [
            "id",
            "loan",
            "installment_number",
            "due_date",
            "paid_date",
            "amount_due",
            "amount_paid",
            "principal_component",
            "interest_component",
            "penalty",
            "balance_after",
            "payment_status",
            "payment_mode",
            "reference_number",
            "receipt",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields


# ========================================
# Fund Serializers
# ========================================


class FundAccountSerializer(serializers.ModelSerializer):
    """Fund account serializer."""

    fund_type_display = serializers.CharField(source="get_fund_type_display", read_only=True)

    class Meta:
        model = FundAccount
        fields = [
            "id",
            "name",
            "fund_type",
            "fund_type_display",
            "account_number",
            "balance",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "account_number", "balance", "created_at", "updated_at"]


class FundTransactionSerializer(serializers.ModelSerializer):
    """Fund transaction serializer."""

    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = FundTransaction
        fields = [
            "id",
            "fund",
            "fund_name",
            "transaction_type",
            "amount",
            "description",
            "payment_mode",
            "reference_number",
            "balance_after",
            "trigger_event",
            "source_member",
            "created_by",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "balance_after", "created_by", "created_at"]


class FundAllocationRuleSerializer(serializers.ModelSerializer):
    """Allocation rule serializer."""

    fund_name = serializers.CharField(source="fund.name", read_only=True)
    trigger_event_display = serializers.CharField(source="get_trigger_event_display", read_only=True)

    class Meta:
        model = FundAllocationRule
        fields = [
            "id",
            "trigger_event",
            "trigger_event_display",
            "fund",
            "fund_name",
            "allocation_type",
            "amount",
            "percentage",
            "is_active",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ========================================
# Audit Log Serializer
# ========================================


class AuditLogSerializer(serializers.ModelSerializer):
    """Audit log serializer."""

    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "user_display",
            "action",
            "entity_type",
            "entity_id",
            "description",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_display(self, obj):
        return obj.user.display_name if obj.user else "System"


class NotificationSerializer(serializers.ModelSerializer):
    """Member notification serializer."""

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

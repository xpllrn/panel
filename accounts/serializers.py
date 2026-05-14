from datetime import date
from decimal import Decimal

from django.db.models import Sum

from rest_framework import serializers

from accounts.models import (
    AuditLog,
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    FundAccount,
    FundAllocationRule,
    FundTransaction,
    Instrument,
    InterestReceivable,
    LoanAccount,
    LoanApplication,
    LoanRepayment,
    MemberAccount,
    MemberAddress,
    MemberKYC,
    MemberNominee,
    Notification,
    ProfitAndLoss,
    ShareCapital,
    SocietyAccount,
    Transaction,
    User,
)
from accounts.utils import (
    ensure_member_submodels,
    nominee_primary,
    user_active_share_capital_total,
    user_active_share_count,
    user_address,
    user_kyc,
    user_primary_share_lot,
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
    """Full serializer for detail views (Phase 2: nested KYC, addresses, nominees, share lots)."""

    display_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    current_address_line1 = serializers.SerializerMethodField()
    current_address_line2 = serializers.SerializerMethodField()
    current_city = serializers.SerializerMethodField()
    current_district = serializers.SerializerMethodField()
    current_state = serializers.SerializerMethodField()
    current_pincode = serializers.SerializerMethodField()
    permanent_same_as_current = serializers.SerializerMethodField()
    permanent_address_line1 = serializers.SerializerMethodField()
    permanent_city = serializers.SerializerMethodField()
    permanent_state = serializers.SerializerMethodField()
    permanent_pincode = serializers.SerializerMethodField()
    kyc_status = serializers.SerializerMethodField()
    aadhar_number = serializers.SerializerMethodField()
    pan_number = serializers.SerializerMethodField()
    voter_id = serializers.SerializerMethodField()
    share_capital_amount = serializers.SerializerMethodField()
    number_of_shares = serializers.SerializerMethodField()
    face_value_per_share = serializers.SerializerMethodField()
    nominee_name = serializers.SerializerMethodField()
    nominee_relationship = serializers.SerializerMethodField()
    nominee_contact = serializers.SerializerMethodField()
    total_deposit_balance = serializers.SerializerMethodField()
    total_loan_outstanding = serializers.SerializerMethodField()

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

    def get_current_address_line1(self, obj):
        a = user_address(obj, "current")
        return a.address_line1 or "" if a else ""

    def get_current_address_line2(self, obj):
        a = user_address(obj, "current")
        return a.address_line2 or "" if a else ""

    def get_current_city(self, obj):
        a = user_address(obj, "current")
        return a.city or "" if a else ""

    def get_current_district(self, obj):
        a = user_address(obj, "current")
        return a.district or "" if a else ""

    def get_current_state(self, obj):
        a = user_address(obj, "current")
        return a.state or "" if a else ""

    def get_current_pincode(self, obj):
        a = user_address(obj, "current")
        return a.pincode or "" if a else ""

    def get_permanent_same_as_current(self, obj):
        p = user_address(obj, "permanent")
        return bool(p.same_as_current) if p else False

    def get_permanent_address_line1(self, obj):
        p = user_address(obj, "permanent")
        return p.address_line1 or "" if p else ""

    def get_permanent_city(self, obj):
        p = user_address(obj, "permanent")
        return p.city or "" if p else ""

    def get_permanent_state(self, obj):
        p = user_address(obj, "permanent")
        return p.state or "" if p else ""

    def get_permanent_pincode(self, obj):
        p = user_address(obj, "permanent")
        return p.pincode or "" if p else ""

    def get_kyc_status(self, obj):
        k = user_kyc(obj)
        return k.kyc_status if k else "pending"

    def get_aadhar_number(self, obj):
        k = user_kyc(obj)
        return k.aadhaar_number or "" if k else ""

    def get_pan_number(self, obj):
        k = user_kyc(obj)
        return k.pan_number or "" if k else ""

    def get_voter_id(self, obj):
        k = user_kyc(obj)
        return k.voter_id or "" if k else ""

    def get_share_capital_amount(self, obj):
        return str(user_active_share_capital_total(obj))

    def get_number_of_shares(self, obj):
        return user_active_share_count(obj)

    def get_face_value_per_share(self, obj):
        lot = user_primary_share_lot(obj)
        return str(lot.face_value_per_share) if lot else "0.00"

    def get_nominee_name(self, obj):
        n = nominee_primary(obj)
        return n.name if n else ""

    def get_nominee_relationship(self, obj):
        n = nominee_primary(obj)
        return n.relationship or "" if n else ""

    def get_nominee_contact(self, obj):
        n = nominee_primary(obj)
        return n.contact or "" if n else ""

    def get_total_deposit_balance(self, obj):
        t = obj.member_accounts.filter(is_deleted=False, status="active").aggregate(s=Sum("balance"))["s"]
        return str(t if t is not None else Decimal("0"))

    def get_total_loan_outstanding(self, obj):
        t = LoanAccount.objects.filter(user=obj, status="active").aggregate(s=Sum("outstanding_balance"))["s"]
        return str(t if t is not None else Decimal("0"))

    def _raw_has(self, key):
        data = self.initial_data
        if data is None:
            return False
        if hasattr(data, "keys"):
            return key in data
        return False

    def _raw_get(self, key, default=None):
        data = self.initial_data
        if data is None:
            return default
        val = data.get(key, default)
        if isinstance(val, list) and val:
            return val[0]
        return val

    def update(self, instance, validated_data):
        ensure_member_submodels(instance)
        self._sync_related_from_payload(instance)
        return super().update(instance, validated_data)

    def _sync_related_from_payload(self, user):
        data = self.initial_data
        if not data:
            return
        partial = self.partial

        def want(key):
            return self._raw_has(key) if partial else True

        # Current address
        cur_keys = (
            "current_address_line1",
            "current_address_line2",
            "current_city",
            "current_district",
            "current_state",
            "current_pincode",
        )
        if not partial or any(self._raw_has(k) for k in cur_keys):
            cur, _ = MemberAddress.objects.get_or_create(
                user=user, address_type="current", defaults={"country": "India"}
            )
            mapping = {
                "address_line1": "current_address_line1",
                "address_line2": "current_address_line2",
                "city": "current_city",
                "district": "current_district",
                "state": "current_state",
                "pincode": "current_pincode",
            }
            changed = False
            for model_attr, payload_key in mapping.items():
                if want(payload_key):
                    val = self._raw_get(payload_key, "")
                    setattr(cur, model_attr, val or None)
                    changed = True
            if changed:
                cur.save()

        # Permanent address
        perm_keys = (
            "permanent_same_as_current",
            "permanent_address_line1",
            "permanent_city",
            "permanent_state",
            "permanent_pincode",
        )
        if not partial or any(self._raw_has(k) for k in perm_keys):
            perm, _ = MemberAddress.objects.get_or_create(
                user=user, address_type="permanent", defaults={"country": "India", "same_as_current": True}
            )
            if want("permanent_same_as_current"):
                v = self._raw_get("permanent_same_as_current")
                if isinstance(v, str):
                    perm.same_as_current = v.lower() in ("true", "1", "yes")
                else:
                    perm.same_as_current = bool(v)
            for model_attr, payload_key in (
                ("address_line1", "permanent_address_line1"),
                ("city", "permanent_city"),
                ("state", "permanent_state"),
                ("pincode", "permanent_pincode"),
            ):
                if want(payload_key):
                    val = self._raw_get(payload_key, "")
                    setattr(perm, model_attr, val or None)
            perm.save()

        # KYC
        kyc_keys = ("kyc_status", "aadhar_number", "pan_number", "voter_id")
        if not partial or any(self._raw_has(k) for k in kyc_keys):
            kyc, _ = MemberKYC.objects.get_or_create(user=user)
            if want("kyc_status"):
                kyc.kyc_status = self._raw_get("kyc_status") or kyc.kyc_status
            if want("aadhar_number"):
                kyc.aadhaar_number = self._raw_get("aadhar_number") or None
            if want("pan_number"):
                kyc.pan_number = self._raw_get("pan_number") or None
            if want("voter_id"):
                kyc.voter_id = self._raw_get("voter_id") or None
            kyc.save()

        # Primary nominee
        nom_keys = ("nominee_name", "nominee_relationship", "nominee_contact")
        if not partial or any(self._raw_has(k) for k in nom_keys):
            nom = nominee_primary(user)
            if nom is None and (not partial or self._raw_get("nominee_name")):
                name = self._raw_get("nominee_name", "") or ""
                if name.strip():
                    nom = MemberNominee.objects.create(user=user, is_primary=True, name=name.strip())
            if nom:
                if want("nominee_name"):
                    v = self._raw_get("nominee_name", "")
                    nom.name = (v or "").strip() or nom.name
                if want("nominee_relationship"):
                    nom.relationship = self._raw_get("nominee_relationship") or None
                if want("nominee_contact"):
                    nom.contact = self._raw_get("nominee_contact") or None
                nom.save()

        # Share capital (single active lot)
        sh_keys = ("number_of_shares", "face_value_per_share", "share_certificate_number", "share_issue_date")
        if not partial or any(self._raw_has(k) for k in sh_keys):
            lot = user_primary_share_lot(user)
            if lot is None:
                n = int(self._raw_get("number_of_shares", 0) or 0)
                if n > 0 or (not partial and self._raw_has("number_of_shares")):
                    issue_raw = self._raw_get("share_issue_date")
                    if issue_raw:
                        if isinstance(issue_raw, date):
                            issue_d = issue_raw
                        else:
                            issue_d = date.fromisoformat(str(issue_raw)[:10])
                    else:
                        issue_d = user.date_of_joining or date.today()
                    fv = Decimal(str(self._raw_get("face_value_per_share", "0") or "0"))
                    lot = ShareCapital.objects.create(
                        user=user,
                        number_of_shares=max(n, 0),
                        face_value_per_share=fv,
                        issue_date=issue_d,
                        certificate_number=self._raw_get("share_certificate_number") or None,
                        status="issued",
                    )
            else:
                if want("number_of_shares"):
                    lot.number_of_shares = int(self._raw_get("number_of_shares", lot.number_of_shares) or 0)
                if want("face_value_per_share"):
                    lot.face_value_per_share = Decimal(
                        str(self._raw_get("face_value_per_share", lot.face_value_per_share))
                    )
                if want("share_certificate_number"):
                    lot.certificate_number = self._raw_get("share_certificate_number") or lot.certificate_number
                if want("share_issue_date"):
                    raw = self._raw_get("share_issue_date")
                    if raw:
                        lot.issue_date = date.fromisoformat(str(raw)[:10]) if not isinstance(raw, date) else raw
                lot.save()


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
        from datetime import date as date_cls

        from accounts.utils import split_full_name

        full_name = validated_data.pop("full_name", "")
        password = validated_data.pop("password", None)
        current_address_line1 = validated_data.pop("current_address_line1", "") or ""
        current_city = validated_data.pop("current_city", "") or ""
        current_state = validated_data.pop("current_state", "") or ""
        current_pincode = validated_data.pop("current_pincode", "") or ""
        aadhar_number = validated_data.pop("aadhar_number", None)
        pan_number = validated_data.pop("pan_number", None)
        first_name, last_name = split_full_name(full_name)

        year = date_cls.today().year
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

        username = member_id.lower().replace("-", "")

        user = User(
            username=username,
            member_id=member_id,
            first_name=first_name,
            last_name=last_name,
            role="member",
            date_of_joining=date_cls.today(),
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
        ensure_member_submodels(user)
        if current_address_line1 or current_city or current_state or current_pincode:
            MemberAddress.objects.filter(user=user, address_type="current").update(
                address_line1=current_address_line1 or None,
                city=current_city or None,
                state=current_state or None,
                pincode=current_pincode or None,
            )
        kyc = user_kyc(user)
        if kyc:
            if aadhar_number:
                kyc.aadhaar_number = aadhar_number
            if pan_number:
                kyc.pan_number = pan_number
            kyc.save()
        return user


class MemberProfileSerializer(serializers.ModelSerializer):
    """Serializer for member's own profile (limited fields)."""

    display_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    current_city = serializers.SerializerMethodField()
    current_state = serializers.SerializerMethodField()
    share_capital_amount = serializers.SerializerMethodField()
    number_of_shares = serializers.SerializerMethodField()

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
            "push_notifications_enabled",
        ]
        read_only_fields = fields

    def get_current_city(self, obj):
        a = user_address(obj, "current")
        return a.city or "" if a else ""

    def get_current_state(self, obj):
        a = user_address(obj, "current")
        return a.state or "" if a else ""

    def get_share_capital_amount(self, obj):
        return str(user_active_share_capital_total(obj))

    def get_number_of_shares(self, obj):
        return user_active_share_count(obj)


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
# Transaction Serializers (formerly Receipt)
# ========================================


class InstrumentSerializer(serializers.ModelSerializer):
    """Read-only payment instrument attached to a transaction."""

    instrument_type_display = serializers.CharField(source="get_instrument_type_display", read_only=True)

    class Meta:
        model = Instrument
        fields = [
            "id",
            "instrument_type",
            "instrument_type_display",
            "amount",
            "cheque_number",
            "drawer_name",
            "drawer_bank",
            "drawer_ifsc",
            "cheque_date",
            "cheque_status",
            "reference_number",
            "upi_vpa",
            "is_cleared",
            "clearing_date",
            "bounce_reason",
            "created_at",
            "updated_at",
        ]


class InstrumentPayloadSerializer(serializers.Serializer):
    """Optional nested write payload for ``TransactionCreateSerializer`` (Phase A2)."""

    instrument_type = serializers.ChoiceField(
        choices=[c[0] for c in Instrument.INSTRUMENT_TYPE_CHOICES if c[0] != "cash"],
        required=False,
    )
    cheque_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    drawer_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    drawer_bank = serializers.CharField(max_length=200, required=False, allow_blank=True)
    drawer_ifsc = serializers.CharField(max_length=11, required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    upi_vpa = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cheque_status = serializers.CharField(max_length=20, required=False, allow_blank=True)
    is_cleared = serializers.BooleanField(required=False, default=False)


class TransactionSerializer(serializers.ModelSerializer):
    """Full transaction serializer."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    account_number = serializers.CharField(source="member_account.account_number", read_only=True)
    transaction_type_display = serializers.CharField(source="get_transaction_type_display", read_only=True)
    instrument = InstrumentSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_number",
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
            "transaction_date",
            "instrument",
            "created_by",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "transaction_number", "balance_after", "created_by", "created_at"]


class TransactionCreateSerializer(serializers.Serializer):
    """Serializer for creating transactions (deposits/withdrawals)."""

    member_account = serializers.IntegerField()
    transaction_type = serializers.ChoiceField(choices=Transaction.TRANSACTION_TYPE_CHOICES)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_mode = serializers.ChoiceField(choices=Transaction.PAYMENT_MODE_CHOICES, default="cash")
    description = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    instrument = InstrumentPayloadSerializer(required=False, allow_null=True)


# ========================================
# Loan Serializers (Phase 3: LoanApplication + LoanAccount)
# ========================================


def loan_merged_list_dict(item):
    """Serialize a LoanListItem for admin/member loan list APIs."""
    app = item.application
    return {
        "id": item.id,
        "list_kind": item.list_kind,
        "loan_number": item.loan_number,
        "user": item.user.id,
        "user_display": item.user.display_name,
        "loan_type": app.loan_type,
        "loan_type_display": app.get_loan_type_display(),
        "status": item.status,
        "status_display": item.get_status_display(),
        "principal_amount": str(app.principal_amount),
        "interest_rate": str(app.interest_rate),
        "tenure_months": app.tenure_months,
        "emi_amount": str(item.emi_amount),
        "outstanding_balance": str(item.outstanding_balance),
        "overdue_amount": str(item.overdue_amount),
        "completion_percentage": item.completion_percentage,
        "is_npa": item.is_npa,
        "application_date": item.application_date.isoformat() if item.application_date else None,
        "disbursement_date": item.disbursement_date.isoformat() if item.disbursement_date else None,
    }


class LoanAccountListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for an active loan account (book row)."""

    user_display = serializers.CharField(source="user.display_name", read_only=True)
    loan_type = serializers.CharField(source="application.loan_type", read_only=True)
    loan_type_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)
    is_npa = serializers.BooleanField(read_only=True)
    list_kind = serializers.SerializerMethodField()
    application_date = serializers.DateField(source="application.application_date", read_only=True)

    class Meta:
        model = LoanAccount
        fields = [
            "list_kind",
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

    def get_list_kind(self, obj):
        return "account"

    def get_loan_type_display(self, obj):
        return obj.application.get_loan_type_display()


# Backwards-compatible alias for code that still imports LoanListSerializer
LoanListSerializer = LoanAccountListSerializer


class LoanDetailSerializer(serializers.ModelSerializer):
    """Full loan account detail (includes application fields for API compatibility)."""

    list_kind = serializers.SerializerMethodField()
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    loan_type = serializers.CharField(source="application.loan_type", read_only=True)
    loan_type_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    interest_type_display = serializers.CharField(source="get_interest_type_display", read_only=True)
    completion_percentage = serializers.FloatField(read_only=True)
    is_npa = serializers.BooleanField(read_only=True)
    npa_category = serializers.CharField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    application_date = serializers.DateField(source="application.application_date", read_only=True)
    approval_date = serializers.DateField(source="application.approval_date", read_only=True, allow_null=True)
    purpose = serializers.CharField(source="application.purpose", read_only=True, allow_null=True)
    guarantor_name = serializers.SerializerMethodField()
    guarantor_member_id = serializers.SerializerMethodField()
    guarantor_contact = serializers.SerializerMethodField()
    collateral_description = serializers.SerializerMethodField()
    approved_by = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True, source="application.approved_by")

    class Meta:
        model = LoanAccount
        fields = [
            "list_kind",
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
            "interest_type_display",
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
        read_only_fields = fields

    def get_list_kind(self, obj):
        return "account"

    def get_loan_type_display(self, obj):
        return obj.application.get_loan_type_display()

    def get_guarantor_name(self, obj):
        g = obj.guarantors.order_by("id").first()
        if g:
            return g.name
        return obj.application.guarantor_name or ""

    def get_guarantor_member_id(self, obj):
        g = obj.guarantors.order_by("id").first()
        if g and g.user_id:
            return g.user.member_id or ""
        return obj.application.guarantor_member_id or ""

    def get_guarantor_contact(self, obj):
        g = obj.guarantors.order_by("id").first()
        if g and g.contact:
            return g.contact
        return obj.application.guarantor_contact or ""

    def get_collateral_description(self, obj):
        return obj.collateral_description or obj.application.collateral_description or ""


class LoanApplicationDetailSerializer(serializers.ModelSerializer):
    """Pending / rejected application detail (no repayment schedule yet)."""

    list_kind = serializers.SerializerMethodField()
    loan_number = serializers.CharField(source="application_number", read_only=True)
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    loan_type_display = serializers.CharField(source="get_loan_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    interest_type_display = serializers.CharField(source="get_interest_type_display", read_only=True)
    emi_amount = serializers.SerializerMethodField()
    total_payable = serializers.SerializerMethodField()
    total_paid = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True, default=Decimal("0"))
    outstanding_balance = serializers.SerializerMethodField()
    overdue_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True, default=Decimal("0"))
    completion_percentage = serializers.FloatField(read_only=True, default=0.0)
    is_npa = serializers.BooleanField(read_only=True, default=False)
    npa_category = serializers.CharField(read_only=True, allow_null=True, default=None)
    npa_date = serializers.DateField(read_only=True, allow_null=True, default=None)
    days_overdue = serializers.IntegerField(read_only=True, default=0)
    disbursement_date = serializers.DateField(read_only=True, allow_null=True, default=None)
    first_emi_date = serializers.DateField(read_only=True, allow_null=True, default=None)
    last_emi_date = serializers.DateField(read_only=True, allow_null=True, default=None)
    closure_date = serializers.DateField(read_only=True, allow_null=True, default=None)
    total_emis = serializers.IntegerField(source="tenure_months", read_only=True)
    emis_paid = serializers.IntegerField(read_only=True, default=0)
    emis_overdue = serializers.IntegerField(read_only=True, default=0)
    processing_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=Decimal("0"))
    disbursement_account = serializers.IntegerField(read_only=True, allow_null=True, default=None)
    approved_by = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)

    class Meta:
        model = LoanApplication
        fields = [
            "list_kind",
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
            "interest_type_display",
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
        read_only_fields = fields

    def get_list_kind(self, obj):
        return "application"

    def get_emi_amount(self, obj):
        return obj.calculate_emi()

    def get_total_payable(self, obj):
        principal = obj.principal_amount
        rate = obj.interest_rate
        tenure = obj.tenure_months
        emi = obj.calculate_emi()
        if rate > 0:
            if obj.interest_type == "flat":
                total_interest = principal * rate * Decimal(str(tenure)) / Decimal("1200")
                return (principal + total_interest).quantize(Decimal("0.01"))
            return (emi * Decimal(str(tenure))).quantize(Decimal("0.01"))
        return principal

    def get_outstanding_balance(self, obj):
        return obj.principal_amount


class LoanCreateSerializer(serializers.Serializer):
    """Serializer for creating a loan application."""

    user = serializers.IntegerField()
    loan_type = serializers.ChoiceField(choices=LoanApplication.LOAN_TYPE_CHOICES)
    principal_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    interest_type = serializers.ChoiceField(choices=LoanApplication.INTEREST_TYPE_CHOICES, default="reducing")
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
            "loan_account",
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
            "transaction",
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
            "financial_period",
            "allocation_rule",
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
            "priority_order",
            "min_threshold",
            "max_cap",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ========================================
# Phase 4: Fees, receivables, P&L, society snapshot
# ========================================


class FinancialPeriodMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialPeriod
        fields = ["id", "label", "start_date", "end_date", "status", "is_active"]
        read_only_fields = fields


class FeeScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeSchedule
        fields = [
            "id",
            "fee_type",
            "name",
            "amount",
            "percentage",
            "applies_to",
            "is_active",
            "effective_date",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class FeeChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCharge
        fields = [
            "id",
            "fee_schedule",
            "user",
            "loan_account",
            "member_account",
            "amount",
            "status",
            "transaction",
            "waived_by",
            "waived_reason",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InterestReceivableSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan_account.loan_number", read_only=True)

    class Meta:
        model = InterestReceivable
        fields = [
            "id",
            "loan_account",
            "loan_number",
            "financial_period",
            "amount_accrued",
            "amount_collected",
            "status",
            "due_date",
            "collected_date",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProfitAndLossSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfitAndLoss
        fields = [
            "id",
            "financial_period",
            "loan_interest_income",
            "processing_fees_income",
            "penalty_income",
            "membership_fees_income",
            "other_income",
            "total_income",
            "deposit_interest_expense",
            "bad_debt_expense",
            "other_expense",
            "total_expense",
            "gross_surplus",
            "fund_allocations_total",
            "net_surplus",
            "calculated_by",
            "calculation_date",
            "is_locked",
            "locked_by",
            "locked_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SocietyAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocietyAccount
        fields = [
            "id",
            "financial_period",
            "total_member_deposits",
            "total_loan_outstanding",
            "total_interest_payable",
            "total_interest_receivable",
            "total_fees_collected",
            "total_fund_balance",
            "net_surplus",
            "last_updated",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "last_updated"]


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


# ========================================
# Financial Period Serializer (Phase A5)
# ========================================


class FinancialPeriodSerializer(serializers.ModelSerializer):
    """Read serializer for FinancialPeriod rows.

    The model field is `label` but the public API exposes it as `name` to match
    the rest of the admin surface (and the body accepted by the create endpoint).
    """

    name = serializers.CharField(source="label", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = FinancialPeriod
        fields = [
            "id",
            "name",
            "label",
            "start_date",
            "end_date",
            "is_active",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "name",
            "label",
            "is_active",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]

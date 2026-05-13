from datetime import date

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

# ==========================================================
# Validators for Indian identity documents
# ==========================================================
pan_validator = RegexValidator(
    regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$", message="PAN must be in format: ABCDE1234F (5 letters, 4 digits, 1 letter)"
)

aadhar_validator = RegexValidator(
    regex=r"^[2-9][0-9]{11}$", message="Aadhaar must be 12 digits and cannot start with 0 or 1"
)

phone_validator = RegexValidator(
    regex=r"^[6-9][0-9]{9}$", message="Phone must be 10 digits starting with 6, 7, 8, or 9"
)

ifsc_validator = RegexValidator(
    regex=r"^[A-Z]{4}0[A-Z0-9]{6}$", message="IFSC must be 11 characters: 4 letters + 0 + 6 alphanumeric"
)

pincode_validator = RegexValidator(regex=r"^[1-9][0-9]{5}$", message="Pincode must be 6 digits and cannot start with 0")


# ==========================================================
# Financial Period
# ==========================================================


class FinancialPeriod(models.Model):
    """Tracks the cooperative society's fiscal year (April-March in India)."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
        ("continuing", "Continuing"),
    ]

    label = models.CharField(max_length=20, verbose_name="Period Label")
    start_date = models.DateField(verbose_name="Period Start")
    end_date = models.DateField(verbose_name="Period End")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    is_active = models.BooleanField(default=True, verbose_name="Currently Active Period")
    created_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_periods_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ["start_date", "end_date"]
        verbose_name = "Financial Period"
        verbose_name_plural = "Financial Periods"

    def __str__(self):
        return f"{self.label} ({self.get_status_display()})"


class User(AbstractUser):
    # 1. Core Identity
    MEMBER_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("nominal", "Nominal"),
        ("associate", "Associate"),
        ("staff", "Staff"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("resign", "Resigned"),
        ("closed", "Closed"),
        ("deceased", "Deceased"),
        ("blacklisted", "Blacklisted"),
    ]

    member_id = models.CharField(
        max_length=50, unique=True, blank=True, null=True, verbose_name="Member ID", db_index=True
    )
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPE_CHOICES, default="regular", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    date_of_joining = models.DateField(blank=True, null=True, verbose_name="Date of Joining")
    inactive_since = models.DateField(blank=True, null=True, verbose_name="Inactive Since")
    exit_date = models.DateField(blank=True, null=True, verbose_name="Exit/Closure Date")
    closure_reason = models.TextField(blank=True, null=True, verbose_name="Reason for Closure")

    # 2. Personal Details
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
    ]

    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Date of Birth")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True, null=True)
    occupation = models.CharField(max_length=200, blank=True, null=True)
    annual_income_bracket = models.CharField(max_length=100, blank=True, null=True)
    education_qualification = models.CharField(max_length=200, blank=True, null=True)

    # 3. Contact Information
    COMM_MODE_CHOICES = [
        ("sms", "SMS"),
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("letter", "Letter"),
    ]

    mobile_primary = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="Primary Mobile", validators=[phone_validator]
    )
    mobile_alternate = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="Alternate Mobile", validators=[phone_validator]
    )
    preferred_comm_mode = models.CharField(max_length=20, choices=COMM_MODE_CHOICES, default="email")
    dnd_enabled = models.BooleanField(default=False, verbose_name="Do Not Disturb")

    # 4. Banking Relationship Flags
    RISK_CATEGORY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    eligible_for_accounts = models.BooleanField(default=True)
    eligible_for_loans = models.BooleanField(default=True)
    eligible_for_dividend = models.BooleanField(default=True)
    eligible_for_voting = models.BooleanField(default=True)
    risk_category = models.CharField(max_length=20, choices=RISK_CATEGORY_CHOICES, default="low")

    # 5. Dividend (share ledger lives in ShareCapital — Phase 2)
    dividend_payable_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_dividend_paid_date = models.DateField(blank=True, null=True)

    # 6. Internal Controls & Compliance
    introducer_member = models.ForeignKey(
        "self", on_delete=models.SET_NULL, blank=True, null=True, related_name="introduced_members"
    )
    introducer_approval_date = models.DateField(blank=True, null=True)
    board_approval_reference = models.CharField(max_length=100, blank=True, null=True)
    aml_check_status = models.CharField(max_length=50, blank=True, null=True, verbose_name="AML Check Status")
    last_compliance_review_date = models.DateField(blank=True, null=True)
    internal_remarks = models.TextField(blank=True, null=True, verbose_name="Internal Notes")

    # 7. User/System Mapping
    portal_access_enabled = models.BooleanField(default=True)

    # 8. Soft-delete support
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    # 9. Legacy fields (keeping for compatibility)
    role = models.CharField(max_length=20, default="member", db_index=True)

    @property
    def display_name(self):
        """Return full display name from first_name + last_name, falling back to username."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    def __str__(self):
        return f"{self.member_id or self.username} - {self.display_name}"

    @property
    def age(self):
        """Calculate age from date of birth"""
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            )
        return None

    def generate_password_from_dob(self):
        """Generate password in format: DDMMFIRSTFOUR (e.g., 0211TANM)"""
        name = f"{self.first_name}{self.last_name}".replace(" ", "")
        if self.date_of_birth and name:
            day = self.date_of_birth.strftime("%d")
            month = self.date_of_birth.strftime("%m")
            first_four = name[:4].upper()
            return f"{day}{month}{first_four}"
        return None

    def reset_password_to_dob(self):
        """Reset password to DOB-based format"""
        new_password = self.generate_password_from_dob()
        if new_password:
            self.set_password(new_password)
            return new_password
        return None

    def get_role_display_name(self):
        """Get the display name for the role"""
        return self.role.title()

    def is_admin_role(self):
        """Check if user has admin role"""
        return self.role == "admin" or self.is_superuser

    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.is_superuser or self.role == "admin"

    # 10. Notification & Verification Settings
    email_notifications = models.BooleanField(default=True, verbose_name="Email Notifications")
    sms_notifications = models.BooleanField(default=False, verbose_name="SMS Notifications")
    push_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Push Notifications",
        help_text="When off, the server will not send FCM messages to this member's devices.",
    )

    # Email verification
    email_verified = models.BooleanField(default=False, verbose_name="Email Verified")
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)

    def send_verification_email(self):
        """Send email verification link to user."""
        from accounts.email_utils import send_verification_email

        return send_verification_email(self)

    def verify_email(self, token):
        """Verify email with provided token."""
        if self.email_verification_token == token and not self.email_verified:
            self.email_verified = True
            self.email_verification_token = None
            self.email_verification_sent_at = None
            self.save(update_fields=["email_verified", "email_verification_token", "email_verification_sent_at"])
            return True
        return False


class MemberKYC(models.Model):
    """KYC and identity documents for a member (one row per user)."""

    KYC_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc")
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS_CHOICES, default="pending")
    kyc_verified_date = models.DateField(blank=True, null=True)
    kyc_verified_by = models.CharField(max_length=200, blank=True, null=True)
    aadhaar_number = models.CharField(
        max_length=12, blank=True, null=True, verbose_name="Aadhaar Number", validators=[aadhar_validator]
    )
    pan_number = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="PAN Number", validators=[pan_validator]
    )
    voter_id = models.CharField(max_length=20, blank=True, null=True, verbose_name="Voter ID")
    passport_number = models.CharField(max_length=20, blank=True, null=True)
    driving_licence = models.CharField(max_length=20, blank=True, null=True)
    aadhaar_copy = models.FileField(upload_to="kyc/aadhar/", blank=True, null=True)
    pan_copy = models.FileField(upload_to="kyc/pan/", blank=True, null=True)
    address_proof = models.FileField(upload_to="kyc/address/", blank=True, null=True)
    photograph = models.ImageField(upload_to="kyc/photos/", blank=True, null=True)
    signature_specimen = models.ImageField(upload_to="kyc/signatures/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Member KYC"
        verbose_name_plural = "Member KYC"

    def __str__(self):
        return f"KYC: {self.user.display_name}"


class MemberNominee(models.Model):
    """Nominee record; primary + additional nominees as separate rows."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="nominees")
    is_primary = models.BooleanField(default=True)
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    contact = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    id_type = models.CharField(max_length=50, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user", "-is_primary", "id"]
        verbose_name = "Member Nominee"
        verbose_name_plural = "Member Nominees"

    def __str__(self):
        return f"{self.name} ({self.user.display_name})"


class MemberAddress(models.Model):
    """Current or permanent postal address for a member."""

    ADDRESS_TYPE_CHOICES = [
        ("current", "Current"),
        ("permanent", "Permanent"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, db_index=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True, validators=[pincode_validator])
    country = models.CharField(max_length=100, default="India")
    same_as_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user", "address_type"]
        unique_together = ["user", "address_type"]
        verbose_name = "Member Address"
        verbose_name_plural = "Member Addresses"

    def __str__(self):
        return f"{self.get_address_type_display()} — {self.user.display_name}"


class ShareCapital(models.Model):
    """Shareholding lots (historical rows possible)."""

    STATUS_CHOICES = [
        ("issued", "Issued"),
        ("redeemed", "Redeemed"),
        ("transferred", "Transferred"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="share_holdings")
    number_of_shares = models.IntegerField(default=0)
    face_value_per_share = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    certificate_number = models.CharField(max_length=50, blank=True, null=True)
    issue_date = models.DateField()
    redemption_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="issued", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        verbose_name = "Share Capital"
        verbose_name_plural = "Share Capital"

    def __str__(self):
        return f"{self.user.display_name} — {self.number_of_shares} sh @ {self.face_value_per_share}"

    def save(self, *args, **kwargs):
        from decimal import Decimal

        n = int(self.number_of_shares or 0)
        fv = self.face_value_per_share if self.face_value_per_share is not None else Decimal("0")
        self.total_value = (Decimal(n) * Decimal(str(fv))).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Notification(models.Model):
    """In-app notifications for members."""

    TYPE_CHOICES = [
        ("general", "General"),
        ("transaction", "Transaction"),
        ("loan", "Loan"),
        ("system", "System"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="general", db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.user.display_name} - {self.title}"


class LoginOTPChallenge(models.Model):
    """Stores login OTP challenges for two-step authentication."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_otp_challenges")
    challenge_token = models.CharField(max_length=64, unique=True, db_index=True)
    otp_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField(db_index=True)
    attempt_count = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    consumed_at = models.DateTimeField(blank=True, null=True)
    request_ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Login OTP Challenge"
        verbose_name_plural = "Login OTP Challenges"

    def __str__(self):
        return f"{self.user.username} - {self.challenge_token}"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class UserDevice(models.Model):
    """Device token registry for push notifications."""

    PLATFORM_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    token = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default="android")
    is_active = models.BooleanField(default=True, db_index=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen"]
        verbose_name = "User Device"
        verbose_name_plural = "User Devices"

    def __str__(self):
        return f"{self.user.username} - {self.platform}"


class MemberAccount(models.Model):
    """
    Internal society account model for member deposits.
    Supports Fixed Deposit (FD), Certificate of Deposit (CD),
    Recurring Deposit (RD), Overdraft (OD), Share Account,
    Sukanya Yojana, and Suputra Yojana.
    """

    ACCOUNT_TYPE_CHOICES = [
        ("fd", "Fixed Deposit"),
        ("cd", "Certificate of Deposit"),
        ("rd", "Recurring Deposit"),
        ("od", "Overdraft"),
        ("share", "Share Account"),
        ("sukanya", "Sukanya Yojana"),
        ("suputra", "Suputra Yojana"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("closed", "Closed"),
        ("frozen", "Frozen"),
        ("matured", "Matured"),
        ("dormant", "Dormant"),
    ]

    # Core Fields
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="member_accounts")
    account_number = models.CharField(max_length=20, unique=True, db_index=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)

    # Financial Details
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Interest Rate (%)")
    principal_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, verbose_name="Principal Amount"
    )
    accrued_interest = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, verbose_name="Accrued Interest"
    )

    # RD-specific fields
    rd_monthly_amount = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="RD Monthly Installment"
    )
    rd_installments_paid = models.IntegerField(default=0, verbose_name="Installments Paid")
    rd_total_installments = models.IntegerField(blank=True, null=True, verbose_name="Total Installments")

    # Dates
    opening_date = models.DateField(verbose_name="Account Opening Date")
    maturity_date = models.DateField(blank=True, null=True, verbose_name="Maturity Date")
    closure_date = models.DateField(blank=True, null=True, verbose_name="Closure Date")
    last_transaction_date = models.DateField(blank=True, null=True)
    last_interest_calc_date = models.DateField(blank=True, null=True)

    # Tenure (for FD/RD/CD)
    tenure_months = models.IntegerField(blank=True, null=True, verbose_name="Tenure (Months)")

    # Nominee (can override member's default nominee)
    nominee_name = models.CharField(max_length=200, blank=True, null=True)
    nominee_relationship = models.CharField(max_length=100, blank=True, null=True)

    # Internal tracking
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft-delete support
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Member Account"
        verbose_name_plural = "Member Accounts"

    def __str__(self):
        return f"{self.account_number} - {self.get_account_type_display()} ({self.user.display_name})"

    @property
    def is_term_deposit(self):
        """Check if account is a term deposit (FD/RD/CD/Sukanya/Suputra)."""
        return self.account_type in ("fd", "rd", "cd", "sukanya", "suputra")

    @property
    def maturity_amount(self):
        """Calculate estimated maturity amount for term deposits."""
        if self.is_term_deposit and self.principal_amount and self.interest_rate and self.tenure_months:
            # Simple interest calculation for estimation
            interest = (self.principal_amount * self.interest_rate * self.tenure_months) / (12 * 100)
            return self.principal_amount + interest
        return self.balance


# ==========================================================
# Instrument (Payment Instrument Tracking)
# ==========================================================


class Instrument(models.Model):
    """Tracks payment instruments — cheques, DDs, NEFT, UPI, IMPS, RTGS."""

    INSTRUMENT_TYPE_CHOICES = [
        ("cash", "Cash"),
        ("cheque", "Cheque"),
        ("dd", "Demand Draft"),
        ("neft", "NEFT"),
        ("rtgs", "RTGS"),
        ("upi", "UPI"),
        ("imps", "IMPS"),
    ]

    CHEQUE_STATUS_CHOICES = [
        ("not_submitted", "Not Submitted"),
        ("submitted", "Submitted"),
        ("cleared", "Cleared"),
        ("bounced", "Bounced"),
        ("cancelled", "Cancelled"),
    ]

    instrument_type = models.CharField(max_length=20, choices=INSTRUMENT_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Cheque / DD fields
    cheque_number = models.CharField(max_length=30, blank=True, null=True)
    drawer_name = models.CharField(max_length=200, blank=True, null=True)
    drawer_bank = models.CharField(max_length=200, blank=True, null=True)
    drawer_ifsc = models.CharField(max_length=11, blank=True, null=True, validators=[ifsc_validator])
    cheque_date = models.DateField(blank=True, null=True)
    cheque_status = models.CharField(
        max_length=20, choices=CHEQUE_STATUS_CHOICES, default="not_submitted", blank=True, null=True
    )

    # Electronic transfer fields
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="UTR / Reference")
    upi_vpa = models.CharField(max_length=100, blank=True, null=True, verbose_name="UPI VPA")

    # Clearing
    is_cleared = models.BooleanField(default=False)
    clearing_date = models.DateField(blank=True, null=True)
    bounce_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Instrument"
        verbose_name_plural = "Instruments"

    def __str__(self):
        return f"{self.get_instrument_type_display()} - ₹{self.amount}"


# ==========================================================
# Transaction (formerly Receipt)
# ==========================================================


class Transaction(models.Model):
    """
    Transaction model for tracking all financial transactions.
    Generates professional bank receipts for credits, debits, and other transactions.
    """

    TRANSACTION_TYPE_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("transfer", "Transfer"),
        ("interest", "Interest Payment"),
        ("dividend", "Dividend"),
        ("share_capital", "Share Capital"),
    ]

    PAYMENT_MODE_CHOICES = [
        ("cash", "Cash"),
        ("cheque", "Cheque"),
        ("online", "Online Transfer"),
        ("neft", "NEFT"),
        ("rtgs", "RTGS"),
        ("upi", "UPI"),
    ]

    # Core Fields
    transaction_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    member_account = models.ForeignKey(MemberAccount, on_delete=models.CASCADE, related_name="transactions")

    # Transaction Details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    # Payment Details
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default="cash")
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Reference / Cheque No.")
    balance_after = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, verbose_name="Balance After Transaction"
    )

    # Date the transaction occurred (vs created_at which is system timestamp)
    transaction_date = models.DateField(blank=True, null=True, verbose_name="Transaction Date")

    # Link to payment instrument for detailed tracking
    instrument = models.ForeignKey(
        Instrument, on_delete=models.SET_NULL, blank=True, null=True, related_name="transactions"
    )

    # Internal tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions_created",
        verbose_name="Created By (Admin)",
    )
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.transaction_number} - {self.get_transaction_type_display()} - {self.amount}"


class Voucher(models.Model):
    """Voucher staging model for pending transactions before settlement."""

    VOUCHER_TYPE_CHOICES = [
        ("receipt", "Receipt Voucher"),
        ("payment", "Payment Voucher"),
        ("contra", "Contra Voucher"),
        ("journal", "Journal Voucher"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("transferred", "Transferred"),
        ("cancelled", "Cancelled"),
    ]

    voucher_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vouchers")
    voucher_type = models.CharField(max_length=20, choices=VOUCHER_TYPE_CHOICES, default="receipt", db_index=True)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    payment_mode = models.CharField(max_length=20, choices=Transaction.PAYMENT_MODE_CHOICES, default="cash")
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    journal_narration = models.TextField(blank=True, null=True, verbose_name="Journal Narration")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="vouchers_created")
    transferred_to_fund = models.ForeignKey(
        "FundAccount", on_delete=models.SET_NULL, blank=True, null=True, related_name="vouchers_transferred"
    )
    transferred_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Voucher"
        verbose_name_plural = "Vouchers"

    def __str__(self):
        return f"{self.voucher_number} - {self.user.display_name}"


class VoucherEntry(models.Model):
    """Line-level account entries captured in a voucher."""

    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name="entries")
    member_account = models.ForeignKey(MemberAccount, on_delete=models.CASCADE, related_name="voucher_entries")
    transaction_type = models.CharField(max_length=20, choices=Transaction.TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    linked_loan_repayment = models.ForeignKey(
        "LoanRepayment", on_delete=models.SET_NULL, blank=True, null=True, related_name="voucher_entries"
    )
    created_transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name="voucher_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Voucher Entry"
        verbose_name_plural = "Voucher Entries"

    def __str__(self):
        return f"{self.voucher.voucher_number} - {self.member_account.account_number}"


class LoanApplication(models.Model):
    """Loan application before approval / disbursement (Phase 3 split)."""

    LOAN_TYPE_CHOICES = [
        ("personal", "Personal Loan"),
        ("home", "Home Loan"),
        ("vehicle", "Vehicle Loan"),
        ("gold", "Gold Loan"),
        ("education", "Education Loan"),
        ("business", "Business Loan"),
        ("emergency", "Emergency Loan"),
        ("agriculture", "Agriculture Loan"),
    ]

    APPLICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    INTEREST_TYPE_CHOICES = [
        ("flat", "Flat Rate"),
        ("reducing", "Reducing Balance"),
    ]

    application_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loan_applications")
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPE_CHOICES, db_index=True)
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPE_CHOICES, default="reducing")
    tenure_months = models.IntegerField()
    purpose = models.TextField(blank=True, null=True)
    # Captured at application time; copied to LoanAccount / Guarantor on approval
    guarantor_name = models.CharField(max_length=200, blank=True, null=True)
    guarantor_member_id = models.CharField(max_length=50, blank=True, null=True)
    guarantor_relationship = models.CharField(max_length=100, blank=True, null=True)
    guarantor_contact = models.CharField(max_length=15, blank=True, null=True)
    collateral_type = models.CharField(max_length=200, blank=True, null=True)
    collateral_value = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    collateral_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, default="pending", db_index=True)
    application_date = models.DateField()
    approval_date = models.DateField(blank=True, null=True)
    rejected_reason = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="applications_approved",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="applications_created"
    )
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Loan Application"
        verbose_name_plural = "Loan Applications"

    def __str__(self):
        return f"{self.application_number} — {self.get_loan_type_display()} ({self.user.display_name})"

    def calculate_emi(self):
        """Proposed EMI from application terms; routes through the flat-rate
        helper when ``interest_type == "flat"`` and reducing-balance otherwise."""
        from accounts.interest import InterestCalculatorService

        if self.interest_type == "flat":
            return InterestCalculatorService.calculate_flat_emi(
                self.principal_amount, self.interest_rate, self.tenure_months
            )
        return InterestCalculatorService.calculate_emi(self.principal_amount, self.interest_rate, self.tenure_months)


class LoanAccount(models.Model):
    """Active loan book entry; one row per disbursed loan, linked 1:1 to an approved application."""

    ACCOUNT_STATUS_CHOICES = [
        ("active", "Active"),
        ("closed", "Closed"),
        ("defaulted", "Defaulted"),
        ("written_off", "Written Off"),
    ]

    loan_number = models.CharField(max_length=20, unique=True, db_index=True)
    application = models.OneToOneField(LoanApplication, on_delete=models.CASCADE, related_name="loan_account")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="loan_accounts")
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default="active", db_index=True)

    principal_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Loan Amount")
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Interest Rate (% p.a.)")
    interest_type = models.CharField(max_length=20, choices=LoanApplication.INTEREST_TYPE_CHOICES, default="reducing")
    tenure_months = models.IntegerField(verbose_name="Tenure (Months)")
    emi_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="EMI Amount")

    total_payable = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    overdue_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    disbursement_date = models.DateField(blank=True, null=True, verbose_name="Disbursement Date")
    first_emi_date = models.DateField(blank=True, null=True, verbose_name="First EMI Date")
    last_emi_date = models.DateField(blank=True, null=True, verbose_name="Last EMI Date")
    closure_date = models.DateField(blank=True, null=True, verbose_name="Closure Date")

    total_emis = models.IntegerField(default=0, verbose_name="Total EMIs")
    emis_paid = models.IntegerField(default=0, verbose_name="EMIs Paid")
    emis_overdue = models.IntegerField(default=0, verbose_name="EMIs Overdue")

    collateral_type = models.CharField(max_length=200, blank=True, null=True, verbose_name="Collateral Type")
    collateral_value = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True, verbose_name="Collateral Value"
    )
    collateral_description = models.TextField(blank=True, null=True, verbose_name="Collateral Description")

    disbursement_account = models.ForeignKey(
        MemberAccount,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="loans_disbursed",
        verbose_name="Disbursement Account",
    )

    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Processing Fee")
    npa_date = models.DateField(blank=True, null=True, verbose_name="NPA Classification Date")

    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="loan_accounts_created", verbose_name="Created By"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Loan Account"
        verbose_name_plural = "Loan Accounts"

    def __str__(self):
        return f"{self.loan_number} — {self.application.get_loan_type_display()} ({self.user.display_name})"

    @property
    def loan_type(self):
        return self.application.loan_type

    def get_loan_type_display(self):
        return self.application.get_loan_type_display()

    @property
    def completion_percentage(self):
        if self.total_emis > 0:
            return round((self.emis_paid / self.total_emis) * 100, 1)
        return 0

    @property
    def is_npa(self):
        if self.status not in ("active", "defaulted"):
            return False
        overdue_repayments = self.repayments.filter(payment_status="overdue", due_date__lt=date.today())
        if overdue_repayments.exists():
            oldest_overdue = overdue_repayments.order_by("due_date").first()
            days_overdue = (date.today() - oldest_overdue.due_date).days
            return days_overdue >= 90
        return False

    @property
    def npa_category(self):
        if not self.is_npa:
            return None
        overdue_repayments = self.repayments.filter(payment_status="overdue", due_date__lt=date.today())
        oldest_overdue = overdue_repayments.order_by("due_date").first()
        days_overdue = (date.today() - oldest_overdue.due_date).days
        if days_overdue >= 1095:
            return "loss"
        elif days_overdue >= 365:
            return "doubtful"
        return "substandard"

    @property
    def days_overdue(self):
        overdue_repayments = self.repayments.filter(payment_status="overdue", due_date__lt=date.today())
        if overdue_repayments.exists():
            oldest = overdue_repayments.order_by("due_date").first()
            return (date.today() - oldest.due_date).days
        return 0

    @property
    def calculated_overdue_amount(self):
        from decimal import Decimal

        overdue = self.repayments.filter(payment_status="overdue", due_date__lt=date.today())
        total = overdue.aggregate(total=Sum("amount_due"))["total"]
        return total or Decimal("0.00")

    def calculate_emi(self):
        """EMI for the active loan; routes through the flat-rate helper when
        ``interest_type == "flat"`` and reducing-balance otherwise."""
        from accounts.interest import InterestCalculatorService

        if self.interest_type == "flat":
            return InterestCalculatorService.calculate_flat_emi(
                self.principal_amount, self.interest_rate, self.tenure_months
            )
        return InterestCalculatorService.calculate_emi(self.principal_amount, self.interest_rate, self.tenure_months)


class Guarantor(models.Model):
    """Guarantor on a loan account (member or external)."""

    loan_account = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name="guarantors")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name="guarantees")
    name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=100, blank=True, null=True)
    contact = models.CharField(max_length=15, blank=True, null=True, validators=[phone_validator])
    is_member = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["loan_account", "created_at"]
        verbose_name = "Guarantor"
        verbose_name_plural = "Guarantors"

    def __str__(self):
        return f"{self.name} ({self.loan_account.loan_number})"


class LoanRepayment(models.Model):
    """
    Tracks individual loan repayment (EMI) payments.
    """

    PAYMENT_STATUS_CHOICES = [
        ("paid", "Paid"),
        ("partial", "Partial"),
        ("overdue", "Overdue"),
        ("upcoming", "Upcoming"),
    ]

    loan_account = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name="repayments")
    installment_number = models.IntegerField(verbose_name="Installment #")

    # Payment Details
    due_date = models.DateField(verbose_name="Due Date")
    paid_date = models.DateField(blank=True, null=True, verbose_name="Paid Date")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Amount Due")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Amount Paid")
    principal_component = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00, verbose_name="Principal Component"
    )
    interest_component = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00, verbose_name="Interest Component"
    )
    penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Late Penalty")
    balance_after = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, verbose_name="Outstanding After Payment"
    )
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="upcoming")

    # Payment mode
    payment_mode = models.CharField(max_length=20, choices=Transaction.PAYMENT_MODE_CHOICES, default="cash")
    reference_number = models.CharField(max_length=100, blank=True, null=True)

    # Linked transaction
    transaction = models.ForeignKey(
        Transaction, on_delete=models.SET_NULL, blank=True, null=True, related_name="loan_repayments"
    )

    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["installment_number"]
        unique_together = ["loan_account", "installment_number"]
        verbose_name = "Loan Repayment"
        verbose_name_plural = "Loan Repayments"

    def __str__(self):
        return f"{self.loan_account.loan_number} - EMI #{self.installment_number}"


class AuditLog(models.Model):
    """
    Audit log model for tracking all admin actions.
    Records who did what, when, and to which entity.
    """

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("approve", "Approve"),
        ("reject", "Reject"),
        ("reset_password", "Reset Password"),
        ("export", "Export"),
    ]

    ENTITY_CHOICES = [
        ("member", "Member"),
        ("account", "Account"),
        ("transaction", "Transaction"),
        ("voucher", "Voucher"),
        ("loan", "Loan"),
        ("fund", "Fund"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs", verbose_name="Performed By"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    entity_type = models.CharField(max_length=20, choices=ENTITY_CHOICES, db_index=True)
    entity_id = models.IntegerField(blank=True, null=True, verbose_name="Entity ID")
    description = models.TextField(verbose_name="Action Description")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        user_display = self.user.display_name if self.user else "System"
        return f"{user_display} - {self.get_action_display()} {self.get_entity_type_display()}"


class FundAccount(models.Model):
    """
    Fund account model for managing society funds.
    Supports various fund types like welfare, library, education, emergency, etc.
    """

    FUND_TYPE_CHOICES = [
        ("welfare", "Welfare Fund"),
        ("library", "Library Fund"),
        ("education", "Education Fund"),
        ("emergency", "Emergency Fund"),
        ("dividend", "Dividend Fund"),
        ("statutory", "Statutory Fund"),
        ("reserve", "Reserve Fund"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200, verbose_name="Fund Name")
    fund_type = models.CharField(max_length=20, choices=FUND_TYPE_CHOICES, db_index=True)
    account_number = models.CharField(max_length=20, unique=True, db_index=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="funds_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft-delete support
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Fund Account"
        verbose_name_plural = "Fund Accounts"

    def __str__(self):
        return f"{self.account_number} - {self.name}"


class FundTransaction(models.Model):
    """
    Fund transaction model for tracking all fund movements.
    Records credits, debits, and auto-allocations from various trigger events.
    """

    TRANSACTION_TYPE_CHOICES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    PAYMENT_MODE_CHOICES = [
        ("cash", "Cash"),
        ("cheque", "Cheque"),
        ("online", "Online Transfer"),
        ("neft", "NEFT"),
        ("rtgs", "RTGS"),
        ("upi", "UPI"),
        ("internal", "Internal Transfer"),
    ]

    fund = models.ForeignKey(FundAccount, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField()
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default="internal")
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    trigger_event = models.CharField(max_length=50, blank=True, null=True)
    source_member = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="fund_transactions"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="fund_transactions_created")
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="fund_transactions",
    )
    allocation_rule = models.ForeignKey(
        "FundAllocationRule",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="fund_transactions",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Fund Transaction"
        verbose_name_plural = "Fund Transactions"

    def __str__(self):
        return f"{self.fund.name} - {self.get_transaction_type_display()} - {self.amount}"


class FundAllocationRule(models.Model):
    """
    Fund allocation rule model for automatic fund allocations.
    Defines rules for allocating amounts to funds based on trigger events.
    """

    TRIGGER_EVENT_CHOICES = [
        ("member_registration", "Member Registration"),
        ("loan_interest", "Loan Interest"),
        ("loan_penalty", "Loan Penalty"),
        ("account_interest", "Account Interest"),
        ("annual_profit", "Annual Profit"),
        ("manual", "Manual"),
    ]

    ALLOCATION_TYPE_CHOICES = [
        ("fixed", "Fixed Amount"),
        ("percentage", "Percentage"),
    ]

    trigger_event = models.CharField(max_length=50, choices=TRIGGER_EVENT_CHOICES, db_index=True)
    fund = models.ForeignKey(FundAccount, on_delete=models.CASCADE, related_name="allocation_rules")
    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="allocation_rules_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    priority_order = models.IntegerField(
        default=0,
        verbose_name="Priority",
        help_text="Lower runs first when multiple rules match the same trigger.",
    )
    min_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Minimum source amount",
        help_text="Skip allocation if trigger total is below this amount.",
    )
    max_cap = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Maximum allocation",
        help_text="Cap this rule’s allocation at this amount (after percentage/fixed calc).",
    )

    class Meta:
        ordering = ["priority_order", "trigger_event", "fund"]
        verbose_name = "Fund Allocation Rule"
        verbose_name_plural = "Fund Allocation Rules"

    def __str__(self):
        return f"{self.get_trigger_event_display()} → {self.fund.name} ({self.get_allocation_type_display()})"


class InterestPayout(models.Model):
    """Records interest paid to members on their deposit accounts."""

    STATUS_CHOICES = [
        ("accrued", "Accrued"),
        ("credited", "Credited"),
    ]

    account = models.ForeignKey(MemberAccount, on_delete=models.CASCADE, related_name="interest_payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    transaction = models.ForeignKey(
        "Transaction",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="interest_payouts",
    )
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="interest_payouts",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="accrued", db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="interest_payouts_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Interest Payout"
        verbose_name_plural = "Interest Payouts"

    def __str__(self):
        return f"{self.account.account_number} - ₹{self.amount} ({self.period_start} to {self.period_end})"


# ==========================================================
# Phase 4: Interest receivable, fees, P&L, society snapshot
# ==========================================================


class InterestReceivable(models.Model):
    """Accrued loan interest due to the society (per loan account / period)."""

    STATUS_CHOICES = [
        ("accrued", "Accrued"),
        ("collected", "Collected"),
        ("written_off", "Written Off"),
    ]

    loan_account = models.ForeignKey("LoanAccount", on_delete=models.CASCADE, related_name="interest_receivables")
    financial_period = models.ForeignKey(
        FinancialPeriod, on_delete=models.SET_NULL, blank=True, null=True, related_name="interest_receivables"
    )
    amount_accrued = models.DecimalField(max_digits=12, decimal_places=2)
    amount_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="accrued", db_index=True)
    due_date = models.DateField()
    collected_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Interest Receivable"
        verbose_name_plural = "Interest Receivables"
        unique_together = [["loan_account", "due_date"]]

    def __str__(self):
        return f"{self.loan_account.loan_number} — ₹{self.amount_accrued} ({self.get_status_display()})"


class FeeSchedule(models.Model):
    """Configurable fee definitions (membership, processing, late payment, etc.)."""

    FEE_TYPE_CHOICES = [
        ("membership", "Membership"),
        ("processing", "Processing"),
        ("late_payment", "Late Payment"),
        ("annual_maintenance", "Annual Maintenance"),
        ("closure", "Closure"),
        ("npa", "NPA"),
    ]
    APPLIES_TO_CHOICES = [
        ("loan", "Loan"),
        ("account", "Account"),
        ("membership", "Membership"),
    ]

    fee_type = models.CharField(max_length=30, choices=FEE_TYPE_CHOICES, db_index=True)
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Percentage of base"
    )
    applies_to = models.CharField(max_length=20, choices=APPLIES_TO_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    effective_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "fee_type"]
        verbose_name = "Fee Schedule"
        verbose_name_plural = "Fee Schedules"

    def __str__(self):
        return f"{self.name} ({self.get_fee_type_display()})"


class FeeCharge(models.Model):
    """Posted fee instance against a member / loan / account."""

    STATUS_CHOICES = [
        ("charged", "Charged"),
        ("waived", "Waived"),
        ("refunded", "Refunded"),
    ]

    fee_schedule = models.ForeignKey(FeeSchedule, on_delete=models.CASCADE, related_name="charges")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fee_charges")
    loan_account = models.ForeignKey(
        "LoanAccount", on_delete=models.CASCADE, blank=True, null=True, related_name="fee_charges"
    )
    member_account = models.ForeignKey(
        MemberAccount, on_delete=models.CASCADE, blank=True, null=True, related_name="fee_charges"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="charged", db_index=True)
    transaction = models.ForeignKey(
        "Transaction", on_delete=models.SET_NULL, blank=True, null=True, related_name="fee_charges"
    )
    waived_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="fee_charges_waived"
    )
    waived_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Fee Charge"
        verbose_name_plural = "Fee Charges"

    def __str__(self):
        return f"{self.user.display_name} — ₹{self.amount} ({self.get_status_display()})"


class ProfitAndLoss(models.Model):
    """Persisted P&L snapshot for a financial period (or ad-hoc run)."""

    financial_period = models.ForeignKey(
        FinancialPeriod, on_delete=models.CASCADE, related_name="profit_and_loss_snapshots"
    )

    loan_interest_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processing_fees_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    penalty_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    membership_fees_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    deposit_interest_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bad_debt_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    gross_surplus = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fund_allocations_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_surplus = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    calculated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="profit_loss_calculations"
    )
    calculation_date = models.DateTimeField()
    is_locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="profit_loss_locked"
    )
    locked_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-calculation_date"]
        verbose_name = "Profit and Loss"
        verbose_name_plural = "Profit and Loss"
        constraints = [
            models.UniqueConstraint(
                fields=["financial_period"],
                name="uniq_profitandloss_financial_period",
            ),
        ]

    def __str__(self):
        return f"P&L {self.financial_period.label} @ {self.calculation_date:%Y-%m-%d}"


class SocietyAccount(models.Model):
    """Society-level balance sheet snapshot (aggregates)."""

    financial_period = models.ForeignKey(FinancialPeriod, on_delete=models.CASCADE, related_name="society_accounts")

    total_member_deposits = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_loan_outstanding = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_interest_payable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_interest_receivable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_fees_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_fund_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_surplus = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_updated"]
        verbose_name = "Society Account Snapshot"
        verbose_name_plural = "Society Account Snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["financial_period"],
                name="uniq_societyaccount_financial_period",
            ),
        ]

    def __str__(self):
        return f"Society snapshot — {self.financial_period.label}"


class SocietyConfiguration(models.Model):
    """Global society settings captured during first-run setup."""

    society_name = models.CharField(max_length=255)
    society_logo = models.ImageField(upload_to="society/logo/", blank=True, null=True)
    late_payment_penalty_per_day = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    setup_completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Society Configuration"
        verbose_name_plural = "Society Configuration"

    def __str__(self):
        return self.society_name


class AccountTypeConfiguration(models.Model):
    """Interest configuration for each account type offered by the society."""

    account_type = models.CharField(max_length=100, unique=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "account_type"]
        verbose_name = "Account Type Configuration"
        verbose_name_plural = "Account Type Configurations"

    def __str__(self):
        return f"{self.get_account_type_display()} ({self.interest_rate}%)"


class LoanTypeConfiguration(models.Model):
    """Interest configuration for each loan product offered by the society."""

    loan_type = models.CharField(max_length=100, unique=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "loan_type"]
        verbose_name = "Loan Type Configuration"
        verbose_name_plural = "Loan Type Configurations"

    def __str__(self):
        return f"{self.get_loan_type_display()} ({self.interest_rate}%)"

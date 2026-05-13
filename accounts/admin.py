from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AccountTypeConfiguration,
    FeeCharge,
    FeeSchedule,
    FinancialPeriod,
    InterestPayout,
    InterestReceivable,
    LoanTypeConfiguration,
    ProfitAndLoss,
    SocietyConfiguration,
    SocietyAccount,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (("Additional Info", {"fields": ("role",)}),)


@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    list_display = ["label", "start_date", "end_date", "status", "is_active"]


@admin.register(InterestPayout)
class InterestPayoutAdmin(admin.ModelAdmin):
    list_display = ["account", "amount", "status", "period_start", "period_end", "transaction", "created_at"]


@admin.register(InterestReceivable)
class InterestReceivableAdmin(admin.ModelAdmin):
    list_display = ["loan_account", "amount_accrued", "amount_collected", "status", "due_date", "financial_period"]


@admin.register(FeeSchedule)
class FeeScheduleAdmin(admin.ModelAdmin):
    list_display = ["name", "fee_type", "applies_to", "amount", "percentage", "is_active", "effective_date"]


@admin.register(FeeCharge)
class FeeChargeAdmin(admin.ModelAdmin):
    list_display = ["user", "fee_schedule", "amount", "status", "loan_account", "created_at"]


@admin.register(ProfitAndLoss)
class ProfitAndLossAdmin(admin.ModelAdmin):
    list_display = [
        "financial_period",
        "total_income",
        "total_expense",
        "net_surplus",
        "calculation_date",
        "is_locked",
    ]


@admin.register(SocietyAccount)
class SocietyAccountAdmin(admin.ModelAdmin):
    list_display = [
        "financial_period",
        "total_member_deposits",
        "total_loan_outstanding",
        "total_interest_receivable",
        "total_fund_balance",
        "last_updated",
    ]


@admin.register(SocietyConfiguration)
class SocietyConfigurationAdmin(admin.ModelAdmin):
    list_display = ["society_name", "late_payment_penalty_per_day", "setup_completed_at", "updated_at"]


@admin.register(AccountTypeConfiguration)
class AccountTypeConfigurationAdmin(admin.ModelAdmin):
    list_display = ["account_type", "interest_rate", "is_active", "display_order"]


@admin.register(LoanTypeConfiguration)
class LoanTypeConfigurationAdmin(admin.ModelAdmin):
    list_display = ["loan_type", "interest_rate", "is_active", "display_order"]

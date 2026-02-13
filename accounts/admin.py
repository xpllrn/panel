from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BankAccount, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("avatar", "phone", "pan_card", "aadhar_card", "work", "work_address", "role")}),
    )


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "account_name", "bank_name", "account_number", "created_at"]
    list_filter = ["bank_name", "created_at"]
    search_fields = ["user__username", "account_name", "bank_name", "account_number"]
    readonly_fields = ["created_at", "updated_at"]

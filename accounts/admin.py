from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import InterestPayout, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("role",)}),
    )


@admin.register(InterestPayout)
class InterestPayoutAdmin(admin.ModelAdmin):
    list_display = ["account", "amount", "period_start", "period_end", "created_at"]

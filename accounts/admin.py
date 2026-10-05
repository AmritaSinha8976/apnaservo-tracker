from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class AppUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("ApnaServo", {"fields": ("full_name", "phone", "designation", "role", "must_change_password")}),)
    list_display = ("username", "full_name", "role", "is_active")

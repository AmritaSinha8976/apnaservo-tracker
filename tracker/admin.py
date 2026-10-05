from django.contrib import admin
from .models import Attendance, DailyReport, Holiday, LoginEvent, Note, WorkItem, Workday


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")
    ordering = ("date",)


for m in (Attendance, DailyReport, LoginEvent, Note, WorkItem, Workday):
    admin.site.register(m)

from django.conf import settings
from django.db import models
from django.utils import timezone

U = settings.AUTH_USER_MODEL


def _lines(text):
    return [l.strip().lstrip("-•*· ").strip() for l in (text or "").splitlines() if l.strip().lstrip("-•*· ").strip()]


class WorkItem(models.Model):
    """Admin-assigned tasks AND member-created work share this table."""
    ADMIN, SELF = "ADMIN", "SELF"
    PENDING, PROGRESS, DONE, BLOCKED = "PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED"
    STATUSES = [(PENDING, "Pending"), (PROGRESS, "In Progress"), (DONE, "Completed"), (BLOCKED, "Blocked")]
    PRIORITIES = [("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=5, choices=[(ADMIN, "Admin assigned"), (SELF, "Self added")])
    created_by = models.ForeignKey(U, on_delete=models.CASCADE, related_name="created_items")
    assigned_to = models.ForeignKey(U, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    priority = models.CharField(max_length=6, choices=PRIORITIES, default="MEDIUM")
    status = models.CharField(max_length=12, choices=STATUSES, default=PENDING)
    due_date = models.DateField(null=True, blank=True)
    work_date = models.DateField(default=timezone.localdate)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def set_status(self, status):
        self.status = status
        self.completed_at = timezone.now() if status == self.DONE else None
        self.save()

    def __str__(self):
        return self.title


class Workday(models.Model):
    ACTIVE, ENDED, AUTO = "ACTIVE", "ENDED", "AUTO_CLOSED"
    STATES = [(ACTIVE, "Active"), (ENDED, "Day ended"), (AUTO, "Not ended")]

    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="workdays")
    date = models.DateField()
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=STATES, default=ACTIVE)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    @classmethod
    def for_today(cls, user):
        obj, _ = cls.objects.get_or_create(user=user, date=timezone.localdate(), defaults={"started_at": timezone.now()})
        return obj

    @classmethod
    def close_stale(cls):
        """Days that were never ended get flagged instead of staying 'Active' forever."""
        cls.objects.filter(state=cls.ACTIVE, date__lt=timezone.localdate()).update(state=cls.AUTO)

    @property
    def hours(self):
        if not self.ended_at:
            return ""
        m = int((self.ended_at - self.started_at).total_seconds() // 60)
        return f"{m // 60}h {m % 60:02d}m"

    def __str__(self):
        return f"{self.user} {self.date}"


class Note(models.Model):
    UPDATE, BLOCKER, REMINDER, ADMIN = "UPDATE", "BLOCKER", "REMINDER", "ADMIN"
    KINDS = [(UPDATE, "Work update"), (BLOCKER, "Blocker"), (REMINDER, "Reminder"), (ADMIN, "For admin / team")]
    workday = models.ForeignKey(Workday, on_delete=models.CASCADE, related_name="notes")
    kind = models.CharField(max_length=10, choices=KINDS, default=UPDATE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DailyReport(models.Model):
    workday = models.OneToOneField(Workday, on_delete=models.CASCADE, related_name="report")
    todays_work = models.TextField("Today's work")
    pending_work = models.TextField(blank=True)
    blockers = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)  # tasks/work as they were when the report was submitted
    submitted_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-workday__date"]

    work_lines = property(lambda s: _lines(s.todays_work))
    pending_lines = property(lambda s: _lines(s.pending_work))
    blocker_lines = property(lambda s: _lines(s.blockers))
    note_lines = property(lambda s: _lines(s.notes))


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.name} ({self.date})"


class Attendance(models.Model):
    PRESENT = "PRESENT"
    HOLIDAY = "HOLIDAY"
    WEEKEND = "WEEKEND"
    ABSENT  = "ABSENT"
    STATUSES = [
        (PRESENT, "Present"),
        (HOLIDAY, "Holiday"),
        (WEEKEND, "Weekend"),
        (ABSENT,  "Absent"),
    ]

    user   = models.ForeignKey(U, on_delete=models.CASCADE, related_name="attendances")
    date   = models.DateField()
    status = models.CharField(max_length=10, choices=STATUSES)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} {self.date} {self.status}"


class CalendarNote(models.Model):
    month = models.PositiveSmallIntegerField()  # 1-12
    year  = models.PositiveSmallIntegerField()
    body  = models.TextField()
    created_by = models.ForeignKey(U, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.year}-{self.month:02d}: {self.body[:40]}"


class Announcement(models.Model):
    body       = models.TextField()
    created_by = models.ForeignKey(U, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.body[:60]


class TaskComment(models.Model):
    work_item  = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="comments")
    author     = models.ForeignKey(U, on_delete=models.CASCADE)
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} on {self.work_item}"


class Notification(models.Model):
    DEADLINE = "DEADLINE"
    ASSIGNED = "ASSIGNED"
    KINDS = [(DEADLINE, "Deadline"), (ASSIGNED, "Assigned")]

    user       = models.ForeignKey(U, on_delete=models.CASCADE, related_name="notifications")
    kind       = models.CharField(max_length=10, choices=KINDS)
    message    = models.CharField(max_length=300)
    work_item  = models.ForeignKey("WorkItem", null=True, blank=True, on_delete=models.CASCADE)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.message[:60]}"


class LoginEvent(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="login_events")
    kind = models.CharField(max_length=6, choices=[("LOGIN", "Login"), ("LOGOUT", "Logout")])
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

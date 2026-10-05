from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Attendance, Holiday, LoginEvent, Notification, WorkItem, Workday


def _ip(request):
    return request.META.get("REMOTE_ADDR") if request else None


def mark_attendance(user):
    from django.utils import timezone
    today = timezone.localdate()
    if today.weekday() == 6:
        status = Attendance.WEEKEND
    elif Holiday.objects.filter(date=today).exists():
        status = Attendance.HOLIDAY
    else:
        status = Attendance.PRESENT
    Attendance.objects.get_or_create(user=user, date=today, defaults={"status": status})


def notify_overdue(user):
    from django.utils import timezone
    today = timezone.localdate()
    overdue = WorkItem.objects.filter(
        assigned_to=user,
        due_date__lt=today,
    ).exclude(status=WorkItem.DONE)

    for item in overdue:
        already = Notification.objects.filter(
            user=user, kind=Notification.DEADLINE, work_item=item, is_read=False
        ).exists()
        if not already:
            Notification.objects.create(
                user=user,
                kind=Notification.DEADLINE,
                work_item=item,
                message=f'Your deadline for "{item.title}" has passed. Please finish it and mark as completed ASAP.',
            )


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    LoginEvent.objects.create(user=user, kind="LOGIN", ip_address=_ip(request))
    if not user.is_admin_role:
        Workday.for_today(user)
        mark_attendance(user)
        notify_overdue(user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user:
        LoginEvent.objects.create(user=user, kind="LOGOUT", ip_address=_ip(request))


@receiver(post_save, sender=WorkItem)
def on_workitem_save(sender, instance, created, **kwargs):
    if created and instance.source == WorkItem.ADMIN and instance.assigned_to:
        due = f" — due {instance.due_date.strftime('%d %b %Y')}" if instance.due_date else ""
        Notification.objects.create(
            user=instance.assigned_to,
            kind=Notification.ASSIGNED,
            work_item=instance,
            message=f'Admin has assigned you a new task: "{instance.title}"{due}.',
        )

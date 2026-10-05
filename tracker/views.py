from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required, member_required
from .forms import MemberForm, NoteForm, ReportForm, TaskCommentForm, TaskEditForm, WorkForm, new_password
from .models import Announcement, Attendance, CalendarNote, DailyReport, Holiday, Note, Notification, TaskComment, WorkItem, Workday

User = get_user_model()
DONE = WorkItem.DONE


def _open_or_done_today(user):
    """Open items carry over to the next day; completed ones show on the day they were finished."""
    return WorkItem.objects.filter(assigned_to=user).filter(~Q(status=DONE) | Q(completed_at__date=timezone.localdate()))


def _snapshot(user):
    def pack(qs):
        return [{"title": i.title, "status": i.get_status_display(), "done": i.status == DONE, "priority": i.get_priority_display()} for i in qs]
    items = _open_or_done_today(user)
    return {"assigned": pack(items.filter(source=WorkItem.ADMIN)), "self": pack(items.filter(source=WorkItem.SELF))}


def _back(request, default="home"):
    nxt = request.POST.get("next", "")
    return redirect(nxt if nxt and url_has_allowed_host_and_scheme(nxt, request.get_host()) else default)


# ───────────────────────── member ─────────────────────────
@login_required
def home(request):
    if request.user.is_admin_role:
        return redirect("admin_dashboard")
    user, today = request.user, timezone.localdate()
    wd = Workday.for_today(user)
    items = _open_or_done_today(user)
    assigned = items.filter(source=WorkItem.ADMIN)
    mine     = items.filter(source=WorkItem.SELF)
    overdue  = items.filter(due_date__lt=today).exclude(status=WorkItem.DONE)
    due_today_ids = set(items.filter(due_date=today).exclude(status=WorkItem.DONE).values_list("pk", flat=True))
    report   = DailyReport.objects.filter(workday=wd).first()
    return render(request, "member/dashboard.html", {
        "wd": wd, "today": today, "report": report,
        "assigned": assigned, "mine": mine,
        "notes": wd.notes.all(), "work_form": WorkForm(), "note_form": NoteForm(),
        "statuses": WorkItem.STATUSES,
        "total_tasks": assigned.count() + mine.count(),
        "overdue_count": overdue.count(),
        "report_pending": report is None,
        "due_today_ids": due_today_ids,
        "announcements": Announcement.objects.filter(is_active=True)[:5],
    })


@member_required
@require_POST
def work_add(request):
    f = WorkForm(request.POST)
    if f.is_valid():
        WorkItem.objects.create(
            title=f.cleaned_data["title"],
            description=f.cleaned_data.get("description", ""),
            due_date=f.cleaned_data.get("due_date"),
            source=WorkItem.SELF, created_by=request.user, assigned_to=request.user
        )
        messages.success(request, "Work added.")
    return redirect("home")


@member_required
@require_POST
def work_delete(request, pk):
    item = get_object_or_404(WorkItem, pk=pk, source=WorkItem.SELF, assigned_to=request.user)
    item.delete()
    messages.success(request, "Work item removed.")
    return redirect("home")


@login_required
def task_detail(request, pk):
    item = get_object_or_404(WorkItem.objects.prefetch_related("comments__author"), pk=pk)
    if not request.user.is_admin_role and item.assigned_to_id != request.user.id:
        raise Http404
    form = TaskCommentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.work_item, c.author = item, request.user
        c.save()
        return redirect("task_detail", pk=pk)
    return render(request, "task_detail.html", {"item": item, "form": form, "comments": item.comments.all()})


@admin_required
def task_edit(request, pk):
    item = get_object_or_404(WorkItem, pk=pk, source=WorkItem.ADMIN)
    form = TaskEditForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect("tasks")
    return render(request, "admin_panel/task_edit.html", {"form": form, "item": item})


@admin_required
@require_POST
def task_delete(request, pk):
    item = get_object_or_404(WorkItem, pk=pk, source=WorkItem.ADMIN)
    item.delete()
    messages.success(request, "Task deleted.")
    return redirect("tasks")


@member_required
@require_POST
def note_add(request):
    f = NoteForm(request.POST)
    if f.is_valid():
        n = f.save(commit=False)
        n.workday = Workday.for_today(request.user)
        n.save()
        messages.success(request, "Note saved.")
    return redirect("home")


@login_required
@require_POST
def item_status(request, pk):
    item = get_object_or_404(WorkItem, pk=pk)
    if not request.user.is_admin_role and item.assigned_to_id != request.user.id:
        raise Http404
    status = request.POST.get("status")
    if status in dict(WorkItem.STATUSES):
        item.set_status(status)
        messages.success(request, "Update saved.")
    return _back(request)


@member_required
def end_day(request):
    wd = Workday.for_today(request.user)
    report = DailyReport.objects.filter(workday=wd).first()
    form = ReportForm(request.POST or None, instance=report)
    if request.method == "POST" and form.is_valid():
        r = form.save(commit=False)
        r.workday = wd
        r.snapshot = _snapshot(request.user)
        if report:
            r.edited_at = timezone.now()
        r.save()
        wd.state, wd.ended_at = Workday.ENDED, timezone.now()
        wd.save()
        logout(request)
        messages.success(request, "Your daily report has been saved. See you tomorrow!")
        return redirect("login")
    return render(request, "member/report.html", {"form": form, "wd": wd, "report": report, "snap": _snapshot(request.user),
                                                  "notes": wd.notes.all()})


@member_required
def my_reports(request):
    reports = DailyReport.objects.filter(workday__user=request.user).select_related("workday")
    return render(request, "member/reports.html", {"reports": reports})


@login_required
def report_detail(request, pk):
    r = get_object_or_404(DailyReport.objects.select_related("workday__user"), pk=pk)
    if not request.user.is_admin_role and r.workday.user_id != request.user.id:
        raise Http404
    return render(request, "report_detail.html", {"r": r, "wd": r.workday, "notes": r.workday.notes.all()})


# ───────────────────────── admin ─────────────────────────
@admin_required
def admin_dashboard(request):
    Workday.close_stale()
    today = timezone.localdate()
    members = User.objects.filter(role="MEMBER", is_active=True).order_by("full_name")
    wds = {w.user_id: w for w in Workday.objects.filter(date=today)}
    reported = set(DailyReport.objects.filter(workday__date=today).values_list("workday__user_id", flat=True))
    rows = []
    for m in members:
        wd = wds.get(m.id)
        tasks = _open_or_done_today(m).filter(source=WorkItem.ADMIN)
        blockers = bool(wd and (wd.notes.filter(kind=Note.BLOCKER).exists() or
                                DailyReport.objects.filter(workday=wd).exclude(blockers="").exists()))
        rows.append({"m": m, "wd": wd, "tasks": tasks.count(), "done": tasks.filter(status=DONE).count(),
                     "blockers": blockers, "report": getattr(wd, "report", None) if wd else None})
    # overdue tasks across all members
    overdue_tasks = WorkItem.objects.filter(
        source=WorkItem.ADMIN, due_date__lt=today
    ).exclude(status=DONE).select_related("assigned_to").order_by("due_date")[:50]
    # recent activity (last 20 comments)
    recent_activity = TaskComment.objects.select_related("author", "work_item").order_by("-created_at")[:20]
    return render(request, "admin_panel/dashboard.html", {
        "today": today, "rows": rows, "total": len(rows),
        "active": sum(1 for w in wds.values() if w.state == Workday.ACTIVE),
        "reports_today": len(reported),
        "missing": [r["m"] for r in rows if r["m"].id not in reported],
        "pending": WorkItem.objects.filter(source=WorkItem.ADMIN).exclude(status=DONE).count(),
        "completed": WorkItem.objects.filter(completed_at__date=today).count(),
        "overdue_tasks": overdue_tasks,
        "recent_activity": recent_activity,
        "announcements": Announcement.objects.filter(is_active=True)[:5],
    })


@admin_required
def members(request):
    q = request.GET.get("q", "").strip()
    qs = User.objects.all().order_by("-is_active", "full_name")
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q))
    return render(request, "admin_panel/members.html", {"members": qs, "q": q})


@admin_required
def member_new(request):
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pwd = form.cleaned_data["password"]
        u = form.save()
        return render(request, "admin_panel/credentials.html", {"m": u, "password": pwd, "created": True})
    return render(request, "admin_panel/member_form.html", {"form": form})


@admin_required
def member_detail(request, pk):
    m = get_object_or_404(User, pk=pk)
    return render(request, "admin_panel/member_detail.html", {
        "m": m, "items": m.items.all()[:50],
        "reports": DailyReport.objects.filter(workday__user=m).select_related("workday")[:30],
        "last_login": m.login_events.filter(kind="LOGIN").first(),
    })


@admin_required
@require_POST
def member_reset_password(request, pk):
    m = get_object_or_404(User, pk=pk)
    pwd = new_password()
    m.set_password(pwd)
    m.must_change_password = True
    m.save()
    return render(request, "admin_panel/credentials.html", {"m": m, "password": pwd, "created": False})


@admin_required
@require_POST
def member_toggle_active(request, pk):
    m = get_object_or_404(User, pk=pk)
    if m.id == request.user.id:
        messages.error(request, "You cannot deactivate your own account.")
    else:
        m.is_active = not m.is_active
        m.save(update_fields=["is_active"])
        messages.success(request, f"{m} is now {'active' if m.is_active else 'deactivated'}.")
    return redirect("member_detail", pk=pk)


@admin_required
def tasks(request):
    form = TaskEditForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.source, t.created_by = WorkItem.ADMIN, request.user
        t.save()
        messages.success(request, "Task created.")
        return redirect("tasks")
    qs = WorkItem.objects.select_related("assigned_to")
    member, status, src = request.GET.get("member", ""), request.GET.get("status", ""), request.GET.get("source", "")
    if member == "none":
        qs = qs.filter(assigned_to__isnull=True)
    elif member.isdigit():
        qs = qs.filter(assigned_to_id=member)
    if status in dict(WorkItem.STATUSES):
        qs = qs.filter(status=status)
    if src in (WorkItem.ADMIN, WorkItem.SELF):
        qs = qs.filter(source=src)
    return render(request, "admin_panel/tasks.html", {
        "form": form, "items": qs[:200], "statuses": WorkItem.STATUSES, "f": {"member": member, "status": status, "source": src},
        "all_members": User.objects.filter(role="MEMBER").order_by("full_name"), "active_members": form.fields["assigned_to"].queryset,
    })


@admin_required
@require_POST
def task_assign(request, pk):
    t = get_object_or_404(WorkItem, pk=pk, source=WorkItem.ADMIN)
    uid = request.POST.get("assigned_to", "")
    t.assigned_to = User.objects.filter(pk=uid, role="MEMBER", is_active=True).first() if uid else None
    t.save()
    messages.success(request, "Assignment updated.")
    return redirect("tasks")


@login_required
def attendance_calendar(request):
    import datetime
    from calendar import monthrange
    today = timezone.localdate()
    try:
        year  = int(request.GET.get("year",  today.year))
        month = int(request.GET.get("month", today.month))
    except ValueError:
        year, month = today.year, today.month
    year  = max(2020, min(year,  today.year + 1))
    month = max(1,    min(month, 12))

    if request.user.is_admin_role:
        uid = request.GET.get("member", "")
        target_user = User.objects.filter(pk=uid, role="MEMBER").first() if uid.isdigit() else None
    else:
        target_user = request.user

    days_in_month = monthrange(year, month)[1]
    holidays = {h.date: h.name for h in Holiday.objects.filter(date__year=year, date__month=month)}
    att_map = {a.date: a.status for a in Attendance.objects.filter(
        user=target_user, date__year=year, date__month=month)} if target_user else {}

    calendar_days = []
    for d in range(1, days_in_month + 1):
        dt = datetime.date(year, month, d)
        is_sunday = dt.weekday() == 6
        status = att_map.get(dt)
        if not status:
            if is_sunday:
                status = Attendance.WEEKEND
            elif dt in holidays:
                status = Attendance.HOLIDAY
            elif dt < today:
                status = Attendance.ABSENT
        calendar_days.append({"date": dt, "status": status, "holiday_name": holidays.get(dt, ""), "is_future": dt > today, "is_sunday": is_sunday})

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1)  if month == 12 else (year, month + 1)

    return render(request, "attendance_calendar.html", {
        "calendar_days": calendar_days, "year": year, "month": month,
        "month_name": datetime.date(year, month, 1).strftime("%B %Y"),
        "prev_y": prev_y, "prev_m": prev_m, "next_y": next_y, "next_m": next_m,
        "target_user": target_user,
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "offset_blanks": range(datetime.date(year, month, 1).weekday()),
        "cal_notes": CalendarNote.objects.filter(year=year, month=month),
        "all_members": User.objects.filter(role="MEMBER").order_by("full_name") if request.user.is_admin_role else None,
        "present_count": sum(1 for d in calendar_days if d["status"] == Attendance.PRESENT),
        "absent_count":  sum(1 for d in calendar_days if d["status"] == Attendance.ABSENT),
        "holiday_count": sum(1 for d in calendar_days if d["status"] == Attendance.HOLIDAY),
    })


@admin_required
@require_POST
def calendar_note_add(request):
    body = request.POST.get("body", "").strip()
    year  = request.POST.get("year")
    month = request.POST.get("month")
    if body and year and month:
        CalendarNote.objects.create(body=body, year=int(year), month=int(month), created_by=request.user)
    return redirect(f"/attendance/?year={year}&month={month}")


@admin_required
@require_POST
def calendar_note_delete(request, pk):
    note = get_object_or_404(CalendarNote, pk=pk)
    year, month = note.year, note.month
    note.delete()
    return redirect(f"/attendance/?year={year}&month={month}")


@admin_required
def reports(request):
    Workday.close_stale()
    date = parse_date(request.GET.get("date", ""))
    member = request.GET.get("member", "")
    qs = DailyReport.objects.select_related("workday__user").order_by("-workday__date", "workday__user__full_name")
    if date:
        qs = qs.filter(workday__date=date)
    if member.isdigit():
        qs = qs.filter(workday__user_id=member)
    missing = []
    if date and not member.isdigit():
        done_ids = DailyReport.objects.filter(workday__date=date).values_list("workday__user_id", flat=True)
        missing = User.objects.filter(role="MEMBER", is_active=True).exclude(id__in=done_ids).order_by("full_name")
    return render(request, "admin_panel/reports.html", {
        "reports": qs[:200], "missing": missing, "date": date, "member": member,
        "all_members": User.objects.filter(role="MEMBER").order_by("full_name"),
    })


@member_required
def notifications_view(request):
    notifs = Notification.objects.filter(user=request.user).select_related("work_item")
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, "notifications.html", {"notifs": notifs})


@member_required
@require_POST
def notification_mark_read(request, pk):
    Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    return redirect(request.POST.get("next", "notifications"))


# ── #2 member task history ──────────────────────────────
@member_required
def my_task_history(request):
    import datetime
    today = timezone.localdate()
    month = int(request.GET.get("month", today.month))
    year  = int(request.GET.get("year",  today.year))
    month = max(1, min(month, 12))
    qs = WorkItem.objects.filter(assigned_to=request.user).filter(
        Q(completed_at__year=year, completed_at__month=month) |
        Q(status=DONE, work_date__year=year, work_date__month=month)
    ).distinct().order_by("-completed_at")
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1)  if month == 12 else (year, month + 1)
    return render(request, "member/task_history.html", {
        "items": qs, "month_name": datetime.date(year, month, 1).strftime("%B %Y"),
        "year": year, "month": month,
        "prev_y": prev_y, "prev_m": prev_m, "next_y": next_y, "next_m": next_m,
    })


# ── #3 announcement board ───────────────────────────────
@admin_required
@require_POST
def announcement_add(request):
    body = request.POST.get("body", "").strip()
    if body:
        Announcement.objects.create(body=body, created_by=request.user)
        messages.success(request, "Announcement posted.")
    return redirect("admin_dashboard")


@admin_required
@require_POST
def announcement_delete(request, pk):
    get_object_or_404(Announcement, pk=pk).delete()
    return redirect("admin_dashboard")


# ── #6 member profile summary ───────────────────────────
@login_required
def profile_summary(request):
    import datetime
    from calendar import monthrange
    today = timezone.localdate()
    month = int(request.GET.get("month", today.month))
    year  = int(request.GET.get("year",  today.year))
    month = max(1, min(month, 12))
    user  = request.user if not request.user.is_admin_role else request.user

    days_in_month = monthrange(year, month)[1]
    working_days  = sum(1 for d in range(1, days_in_month + 1)
                        if datetime.date(year, month, d).weekday() != 6)
    present = Attendance.objects.filter(user=user, date__year=year, date__month=month, status=Attendance.PRESENT).count()
    completed_tasks = WorkItem.objects.filter(
        assigned_to=user, status=WorkItem.DONE,
        completed_at__year=year, completed_at__month=month
    ).count()
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1)  if month == 12 else (year, month + 1)
    return render(request, "member/profile_summary.html", {
        "month_name": datetime.date(year, month, 1).strftime("%B %Y"),
        "year": year, "month": month,
        "present": present, "working_days": working_days,
        "attendance_pct": round(present / working_days * 100) if working_days else 0,
        "completed_tasks": completed_tasks,
        "prev_y": prev_y, "prev_m": prev_m, "next_y": next_y, "next_m": next_m,
    })


# ── #7 search ───────────────────────────────────────────
@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    task_results, report_results = [], []
    if q:
        task_qs = WorkItem.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )
        if not request.user.is_admin_role:
            task_qs = task_qs.filter(assigned_to=request.user)
        task_results = task_qs.select_related("assigned_to")[:30]

        report_qs = DailyReport.objects.filter(
            Q(todays_work__icontains=q) | Q(pending_work__icontains=q) | Q(blockers__icontains=q)
        ).select_related("workday__user")
        if not request.user.is_admin_role:
            report_qs = report_qs.filter(workday__user=request.user)
        report_results = report_qs[:30]
    return render(request, "search_results.html", {"q": q, "task_results": task_results, "report_results": report_results})


# ── #8 CSV exports ──────────────────────────────────────
@admin_required
def export_attendance_csv(request):
    import csv
    from django.http import HttpResponse
    from calendar import monthrange
    import datetime
    today = timezone.localdate()
    month = int(request.GET.get("month", today.month))
    year  = int(request.GET.get("year",  today.year))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="attendance_{year}_{month:02d}.csv"'
    writer = csv.writer(response)
    days = monthrange(year, month)[1]
    dates = [datetime.date(year, month, d) for d in range(1, days + 1)]
    writer.writerow(["Member"] + [d.strftime("%d %b") for d in dates] + ["Present", "Absent"])
    members = User.objects.filter(role="MEMBER", is_active=True).order_by("full_name")
    for m in members:
        att = {a.date: a.status for a in Attendance.objects.filter(user=m, date__year=year, date__month=month)}
        row = [m.full_name]
        present = absent = 0
        for d in dates:
            s = att.get(d, "WEEKEND" if d.weekday() == 6 else "")
            row.append(s)
            if s == "PRESENT": present += 1
            elif s == "ABSENT": absent += 1
        row += [present, absent]
        writer.writerow(row)
    return response


@admin_required
def export_reports_csv(request):
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="daily_reports.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Member", "Login", "Logout", "Today's Work", "Pending", "Blockers"])
    qs = DailyReport.objects.select_related("workday__user").order_by("-workday__date")
    date = parse_date(request.GET.get("date", ""))
    member = request.GET.get("member", "")
    if date:
        qs = qs.filter(workday__date=date)
    if member.isdigit():
        qs = qs.filter(workday__user_id=member)
    for r in qs[:500]:
        writer.writerow([
            r.workday.date, r.workday.user.full_name,
            r.workday.started_at.strftime("%H:%M"),
            r.workday.ended_at.strftime("%H:%M") if r.workday.ended_at else "",
            r.todays_work, r.pending_work, r.blockers,
        ])
    return response

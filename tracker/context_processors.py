def notifications(request):
    if request.user.is_authenticated and not getattr(request.user, "is_admin_role", False):
        from tracker.models import Notification
        return {"unread_count": Notification.objects.filter(user=request.user, is_read=False).count()}
    return {"unread_count": 0}

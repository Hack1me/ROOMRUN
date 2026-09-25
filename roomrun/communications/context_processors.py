from communications.models import Notification


def notification_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_notification_count": 0}
    return {
        "unread_notification_count": Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
    }

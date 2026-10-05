from communications.models import Notification


def send_notification(
    *, recipient, title, message, notification_type, related_object=None
):
    """Persist an in-app notification for an authenticated ROOMRUN user."""
    if recipient is None:
        return None
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        related_object=related_object,
    )

from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import Announcement
from .models import Message
from .models import Notification


@receiver(pre_save, sender=Announcement)
def set_announcement_number(sender, instance, **kwargs):
    """Auto-generate announcement_number if not already set."""
    if instance._state.adding and not instance.announcement_number:
        assign_reference_identifier(
            instance, field="announcement_number", prefix="ANN"
        )


@receiver(pre_save, sender=Notification)
def set_notification_number(sender, instance, **kwargs):
    """Auto-generate notification_number if not already set."""
    if instance._state.adding and not instance.notification_number:
        assign_reference_identifier(
            instance, field="notification_number", prefix="NTF"
        )


@receiver(pre_save, sender=Message)
def set_message_number(sender, instance, **kwargs):
    """Auto-generate message_number if not already set."""
    if instance._state.adding and not instance.message_number:
        assign_reference_identifier(
            instance, field="message_number", prefix="MSG"
        )

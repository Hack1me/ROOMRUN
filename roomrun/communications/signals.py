from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from utils.helpers import assign_reference_identifier

from .models import Announcement
from .models import ConversationParticipant
from .models import Message
from .models import Notification


@receiver(pre_save, sender=Announcement)
def set_announcement_number(sender, instance, **kwargs):
    """Auto-generate announcement_number if not already set."""
    if instance._state.adding and not instance.announcement_number:  # noqa: SLF001
        assign_reference_identifier(instance, field="announcement_number", prefix="ANN")


@receiver(pre_save, sender=Notification)
def set_notification_number(sender, instance, **kwargs):
    """Auto-generate notification_number if not already set."""
    if instance._state.adding and not instance.notification_number:  # noqa: SLF001
        assign_reference_identifier(instance, field="notification_number", prefix="NTF")


@receiver(pre_save, sender=Message)
def set_message_number(sender, instance, **kwargs):
    """Auto-generate message_number if not already set."""
    if instance._state.adding and not instance.message_number:  # noqa: SLF001
        assign_reference_identifier(instance, field="message_number", prefix="MSG")


@receiver(post_save, sender=Message)
def update_conversation_last_message_at(sender, instance, created, **kwargs):
    """Denormalize the last message timestamp on the conversation."""
    if created:
        conversation = instance.conversation
        conversation.last_message_at = instance.created_at
        conversation.save(update_fields=["last_message_at", "updated_at"])


def validate_message_sender(sender, instance, **kwargs):
    """
    Ensure the message sender is actually a participant of the conversation.
    Call this from the service layer before save, or via pre_save if you prefer.
    """
    if instance.sender_id and instance.conversation_id:
        is_participant = ConversationParticipant.objects.filter(
            conversation_id=instance.conversation_id,
            user_id=instance.sender_id,
        ).exists()
        if not is_participant:
            raise ValidationError(
                _("The sender is not a participant of this conversation.")
            )

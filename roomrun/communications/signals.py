import uuid

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Announcement


@receiver(pre_save, sender=Announcement)
def set_announcement_number(sender, instance, **kwargs):
    """Auto-generate announcement_number if not already set."""
    if not instance.announcement_number:
        instance.announcement_number = f"ANN-{uuid.uuid4().hex[:8].upper()}"

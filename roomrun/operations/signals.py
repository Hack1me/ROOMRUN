import uuid

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import CleaningSchedule


@receiver(pre_save, sender=CleaningSchedule)
def set_schedule_number(sender, instance, **kwargs):
    """Auto-generate schedule_number if not already set."""
    if not instance.schedule_number:
        instance.schedule_number = f"CLS-{uuid.uuid4().hex[:8].upper()}"

from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import CleaningSchedule


@receiver(pre_save, sender=CleaningSchedule)
def set_schedule_number(sender, instance, **kwargs):
    """Auto-generate schedule_number if not already set."""
    assign_reference_identifier(instance, field="schedule_number", prefix="CLS")

from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import CleaningSchedule


@receiver(pre_save, sender=CleaningSchedule)
def set_schedule_number(sender, instance, **kwargs):
    """Auto-generate schedule_number if not already set."""
    if not instance.schedule_number:
        instance.schedule_number = generate_unique_identifier(
            prefix="CLS",
            model=CleaningSchedule,
            field="schedule_number",
        )

from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import Announcement


@receiver(pre_save, sender=Announcement)
def set_announcement_number(sender, instance, **kwargs):
    """Auto-generate announcement_number if not already set."""
    assign_reference_identifier(instance, field="announcement_number", prefix="ANN")

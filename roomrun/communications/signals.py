from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import Announcement


@receiver(pre_save, sender=Announcement)
def set_announcement_number(sender, instance, **kwargs):
    """Auto-generate announcement_number if not already set."""
    if not instance.announcement_number:
        instance.announcement_number = generate_unique_identifier(
            prefix="ANN",
            model=Announcement,
            field="announcement_number",
        )

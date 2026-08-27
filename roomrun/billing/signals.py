import uuid

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Charge


@receiver(pre_save, sender=Charge)
def set_charge_number(sender, instance, **kwargs):
    """Auto-generate charge_number if not already set."""
    if not instance.charge_number:
        instance.charge_number = f"CHG-{uuid.uuid4().hex[:8].upper()}"

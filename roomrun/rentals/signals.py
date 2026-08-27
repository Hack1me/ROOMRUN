import uuid

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import RentalApplication
from .models import RentalContract


@receiver(pre_save, sender=RentalApplication)
def set_application_number(sender, instance, **kwargs):
    """Auto-generate application_number if not already set."""
    if not instance.application_number:
        instance.application_number = f"APP-{uuid.uuid4().hex[:8].upper()}"

@receiver(pre_save, sender=RentalContract)
def set_contract_number(sender, instance, **kwargs):
    """Auto-generate contract_number if not already set."""
    if not instance.contract_number:
        instance.contract_number = f"CNT-{uuid.uuid4().hex[:8].upper()}"

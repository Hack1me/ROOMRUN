from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import RentalApplication
from .models import RentalContract


@receiver(pre_save, sender=RentalApplication)
def set_application_number(sender, instance, **kwargs):
    """Auto-generate application_number if not already set."""
    assign_reference_identifier(instance, field="application_number", prefix="APP")


@receiver(pre_save, sender=RentalContract)
def set_contract_number(sender, instance, **kwargs):
    """Auto-generate contract_number if not already set."""

    assign_reference_identifier(instance, field="contract_number", prefix="CNT")

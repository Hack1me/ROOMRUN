from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import RentalApplication
from .models import RentalContract


@receiver(pre_save, sender=RentalApplication)
def set_application_number(sender, instance, **kwargs):
    """Auto-generate application_number if not already set."""
    if not instance.application_number:
        instance.application_number = generate_unique_identifier(
            prefix="APP",
            model=RentalApplication,
            field="application_number",
        )


@receiver(pre_save, sender=RentalContract)
def set_contract_number(sender, instance, **kwargs):
    """Auto-generate contract_number if not already set."""

    if not instance.contract_number:
        instance.contract_number = generate_unique_identifier(
            prefix="CNT",
            model=RentalContract,
            field="contract_number",
        )

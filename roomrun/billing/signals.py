from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import assign_reference_identifier

from .models import Charge
from .models import Payment
from .models import Receipt


@receiver(pre_save, sender=Charge)
def set_charge_number(sender, instance, **kwargs):
    """Auto-generate charge_number if not already set."""
    assign_reference_identifier(instance, field="charge_number", prefix="CHG")


@receiver(pre_save, sender=Payment)
def set_payment_number(sender, instance, **kwargs):
    """Auto-generate payment_number if not already set."""
    assign_reference_identifier(instance, field="payment_number", prefix="PAY")


@receiver(pre_save, sender=Receipt)
def set_receipt_number(sender, instance, **kwargs):
    """Auto-generate receipt_number if not already set."""
    assign_reference_identifier(instance, field="receipt_number", prefix="RCP")

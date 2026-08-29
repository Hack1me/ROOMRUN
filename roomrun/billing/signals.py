from django.db.models.signals import pre_save
from django.dispatch import receiver
from utils.helpers import generate_unique_identifier

from .models import Charge
from .models import Payment
from .models import Receipt


@receiver(pre_save, sender=Charge)
def set_charge_number(sender, instance, **kwargs):
    """Auto-generate charge_number if not already set."""
    if not instance.charge_number:
        instance.charge_number = generate_unique_identifier(
            prefix="CHG",
            model=Charge,
            field="charge_number",
        )


@receiver(pre_save, sender=Payment)
def set_payment_number(sender, instance, **kwargs):
    """Auto-generate payment_number if not already set."""
    if not instance.payment_number:
        instance.payment_number = generate_unique_identifier(
            prefix="PAY",
            model=Payment,
            field="payment_number",
        )


@receiver(pre_save, sender=Receipt)
def set_receipt_number(sender, instance, **kwargs):
    """Auto-generate receipt_number if not already set."""
    if not instance.receipt_number:
        instance.receipt_number = generate_unique_identifier(
            prefix="RCP",
            model=Receipt,
            field="receipt_number",
        )

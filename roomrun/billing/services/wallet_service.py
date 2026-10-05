from billing.models import Payment
from billing.models import Withdrawal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money
from users.models import Landlord
from utils.enums import PaymentStatus


def wallet_balance(landlord):
    """Return settled payments less pending and completed withdrawals."""
    credit_total = Payment.objects.filter(
        charge__contract__unit__building__property_ref__landlord=landlord,
        status=PaymentStatus.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"]
    debit_total = Withdrawal.objects.filter(
        landlord=landlord,
        status__in=[Withdrawal.Status.PENDING, Withdrawal.Status.COMPLETED],
    ).aggregate(total=Sum("amount"))["total"]
    return Money(credit_total or 0, "XAF") - Money(debit_total or 0, "XAF")


def validate_withdrawal_amount(amount, balance):
    """Raise a field validation error when a withdrawal exceeds the balance."""
    amount = Money(amount, "XAF")
    if amount > balance:
        raise ValidationError(
            {"amount": _("The requested amount exceeds your available balance.")}
        )
    return amount


@transaction.atomic
def request_withdrawal(*, landlord, amount, phone_number):
    """Reserve available wallet funds for a landlord withdrawal."""
    Landlord.objects.select_for_update().get(pk=landlord.pk)
    balance = wallet_balance(landlord)
    amount = validate_withdrawal_amount(amount, balance)
    return Withdrawal.objects.create(
        landlord=landlord, amount=amount, phone_number=phone_number
    )

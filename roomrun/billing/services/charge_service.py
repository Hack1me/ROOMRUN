from billing.models import Charge
from communications.services.notification_ser import send_notification
from core.utils.enums import ChargeStatus
from core.utils.enums import ChargeType
from core.utils.enums import ContractStatus
from core.utils.enums import NotificationType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money
from rentals.models import RentalContract


class ChargeService:
    """Create landlord-billed charges without bypassing contract ownership."""

    SYSTEM_MANAGED_TYPES = {ChargeType.INITIAL_PAYMENT, ChargeType.CONTRACT_EXTENSION}

    @staticmethod
    @transaction.atomic
    def create_for_landlord(*, landlord, data, actor=None):
        contract = data["contract"]
        charge_type = data["charge_type"]
        if charge_type in ChargeService.SYSTEM_MANAGED_TYPES:
            raise ValidationError(
                _("This charge type is created automatically by its contract workflow.")
            )
        contract = (
            RentalContract.objects.select_for_update()
            .select_related("tenant__user")
            .filter(
                pk=contract.pk,
                unit__building__property_ref__landlord=landlord,
                status=ContractStatus.ACTIVE,
            )
            .first()
        )
        if contract is None:
            raise ValidationError(
                _("Charges can only be added to an active contract you manage.")
            )
        due_date = data["due_date"]
        if charge_type == ChargeType.RENT and Charge.objects.filter(
            contract=contract,
            charge_type=ChargeType.RENT,
            due_date__year=due_date.year,
            due_date__month=due_date.month,
        ).exclude(status=ChargeStatus.CANCELLED).exists():
            raise ValidationError(
                _("A rent charge already exists for this contract and month.")
            )
        charge = Charge(
            contract=contract,
            charge_type=charge_type,
            amount=Money(data["amount"], contract.monthly_rent.currency),
            due_date=due_date,
            description=data.get("description", "").strip(),
            created_by=actor,
        )
        charge.full_clean()
        charge.save()
        send_notification(
            recipient=contract.tenant.user,
            title=_("New charge on your rental contract"),
            message=_("A %(type)s charge of %(amount)s FCFA is due on %(date)s.")
            % {
                "type": charge.get_charge_type_display(),
                "amount": f"{charge.amount.amount:,.0f}",
                "date": charge.due_date,
            },
            notification_type=NotificationType.PAYMENT,
            related_object=charge,
        )
        return charge

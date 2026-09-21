from typing import TYPE_CHECKING

from billing.models import Charge
from billing.models import Payment
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Unit
from rentals.models import RentalApplication
from rentals.models import RentalContract
from utils.enums import ApplicationStatus
from utils.enums import ChargeType
from utils.enums import ContractStatus
from utils.enums import PaymentMethod
from utils.enums import PaymentStatus
from utils.enums import UnitStatus

if TYPE_CHECKING:
    from djmoney.money import Money


class RentalApplicationService:
    """Business logic related to rental applications."""

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> RentalApplication:
        """Create a new rental application (status forced to PENDING)."""
        data = dict(data)

        # Prevent the caller from controlling these fields.
        for forbidden in ("tenant", "status", "reviewed_by", "reviewed_at"):
            data.pop(forbidden, None)

        application = RentalApplication(
            tenant=tenant,
            status=ApplicationStatus.PENDING,
            **data,
        )
        application.full_clean()
        application.save()

        return application

    # -------------------------------------------------------------------------
    # Review (shared by approve / reject)
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def _review(
        *,
        application: RentalApplication,
        reviewer,
        new_status: str,
    ) -> RentalApplication:
        """
        Internal helper: lock the application, ensure it's pending,
        and transition it to the target status.
        """
        # Re-fetch with a row lock to prevent concurrent reviews.
        application = (
            RentalApplication.objects
            .select_for_update()
            .get(pk=application.pk)
        )

        if application.status != ApplicationStatus.PENDING:
            raise ValidationError(
                _("This application has already been reviewed.")
            )

        application.status = new_status
        application.reviewed_at = timezone.now()
        application.reviewed_by = reviewer

        application.save(
            update_fields=[
                "status",
                "reviewed_at",
                "reviewed_by",
                "updated_at",
            ]
        )

        return application

    @staticmethod
    @transaction.atomic
    def approve(*, application, reviewer) -> RentalApplication:
        """Approve a pending rental application."""
        return RentalApplicationService._review(
            application=application,
            reviewer=reviewer,
            new_status=ApplicationStatus.APPROVED,
        )

    @staticmethod
    @transaction.atomic
    def reject(*, application, reviewer) -> RentalApplication:
        """Reject a pending rental application."""
        return RentalApplicationService._review(
            application=application,
            reviewer=reviewer,
            new_status=ApplicationStatus.REJECTED,
        )

    # -------------------------------------------------------------------------
    # Cancel (by tenant)
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def cancel(*, application: RentalApplication) -> RentalApplication:
        """Cancel a pending rental application (typically by the tenant)."""
        application = (
            RentalApplication.objects
            .select_for_update()
            .get(pk=application.pk)
        )

        if application.status != ApplicationStatus.PENDING:
            raise ValidationError(
                _("Only pending applications can be cancelled.")
            )

        application.status = ApplicationStatus.CANCELLED
        application.save(update_fields=["status", "updated_at"])

        return application



class RentalContractService:
    """Business logic related to rental contracts."""

    # -------------------------------------------------------------------------
    # Create — landlord signs
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create(
        *,
        tenant,
        unit: Unit,
        data: dict,
        application: RentalApplication | None = None,
        landlord_signature=None,
    ) -> RentalContract:
        """
        Create a rental contract after the landlord signs it.

        Contract starts in SIGNING. The unit remains AVAILABLE until
        the tenant signs (see `sign_by_tenant`).
        """
        # 1. Validate landlord signature
        if not landlord_signature:
            raise ValidationError(_("The landlord's signature is required."))

        # 2. Sanitize incoming data
        data = dict(data)
        for forbidden in (
            "tenant", "unit", "application", "status",
            "landlord_signature", "landlord_signed_at",
            "tenant_signature", "tenant_signed_at",
        ):
            data.pop(forbidden, None)

        # 3. Lock and validate the unit
        unit = Unit.objects.select_for_update().get(pk=unit.pk)
        if unit.status != UnitStatus.AVAILABLE:
            raise ValidationError(_("This unit is no longer available."))

        if RentalContract.objects.filter(
            unit=unit,
            status__in=(ContractStatus.ACTIVE, ContractStatus.SIGNING),
        ).exists():
            raise ValidationError(
                _("This unit already has a contract in progress.")
            )

        # 4. Lock and validate the application
        if application:
            application = (
                RentalApplication.objects
                .select_for_update()
                .get(pk=application.pk)
            )

            if application.status != ApplicationStatus.APPROVED:
                raise ValidationError(
                    _("Only approved applications can create a contract.")
                )
            if application.tenant_id != tenant.pk:
                raise ValidationError(
                    _("The application tenant does not match the contract tenant.")
                )
            if application.unit_id != unit.pk:
                raise ValidationError(
                    _("The application unit does not match the contract unit.")
                )
            if RentalContract.objects.filter(application=application).exists():
                raise ValidationError(_("This application already has a contract."))

        # 5. Create the contract
        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            application=application,
            status=ContractStatus.SIGNING,
            landlord_signature=landlord_signature,
            landlord_signed_at=timezone.now(),
            **data,
        )
        contract.full_clean()
        contract.save()

        return contract

    # -------------------------------------------------------------------------
    # Tenant signs → contract becomes ACTIVE, unit becomes OCCUPIED
    # -------------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def sign_by_tenant(
        *,
        contract: RentalContract,
        tenant_signature,
    ) -> RentalContract:
        """
        Record the tenant's signature.

        The contract remains inactive until the initial payment
        has been successfully validated.
        """
        if not tenant_signature:
            raise ValidationError(
                _("The tenant's signature is required.")
            )

        contract = (
            RentalContract.objects
            .select_for_update()
            .get(pk=contract.pk)
        )

        if contract.status != ContractStatus.SIGNING:
            raise ValidationError(
                _("This contract is not awaiting the tenant's signature.")
            )

        contract.tenant_signature = tenant_signature
        contract.tenant_signed_at = timezone.now()
        contract.status = ContractStatus.SIGNED

        contract.save(
            update_fields=[
                "tenant_signature",
                "tenant_signed_at",
                "status",
                "updated_at",
            ]
        )

        return contract

    # -------------------------------------------------------------------------
    # Cancel a contract that is still being signed
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def cancel_signing(
        *,
        contract: RentalContract,
        reason: str = "",
    ) -> RentalContract:
        """
        Cancel a contract still in SIGNING status.

        The unit is freed (stays AVAILABLE) and the contract is cancelled.
        """
        contract = (
            RentalContract.objects
            .select_for_update()
            .get(pk=contract.pk)
        )

        if contract.status != ContractStatus.SIGNING:
            raise ValidationError(
                _("Only contracts in signing can be cancelled this way.")
            )

        contract.status = ContractStatus.CANCELLED
        contract.save(update_fields=["status", "updated_at"])

        return contract


    # -------------------------------------------------------------------------
    # Activate a signed contract after payment
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def activate(
        *,
        contract: RentalContract,
    ) -> RentalContract:
        """
        Activate a signed rental contract after successful payment.

        The contract must be SIGNED by both parties, and a completed
        payment must exist. On success, the contract becomes ACTIVE
        and the unit becomes OCCUPIED.

        Lock order: contract → unit (documented for deadlock prevention).
        """
        # --- 1. Lock and validate the contract ---
        contract = (
            RentalContract.objects
            .select_for_update()
            .select_related("unit")
            .get(pk=contract.pk)
        )

        if contract.status != ContractStatus.SIGNED:
            raise ValidationError(
                _("Only a signed contract can be activated.")
            )

        if not contract.landlord_signature:
            raise ValidationError(_("The landlord's signature is missing."))

        if not contract.tenant_signature:
            raise ValidationError(_("The tenant's signature is missing."))

        # --- 2. Ensure the contract has been paid ---
        # (assuming a related Payment model with FK to contract)
        if not hasattr(contract, "payment") or contract.payment is None:
            raise ValidationError(
                _("This contract cannot be activated until payment is completed.")
            )

        if contract.payment.status != PaymentStatus.COMPLETED:
            raise ValidationError(
                _("The payment for this contract is not yet completed.")
            )

        # --- 3. Lock and validate the unit ---
        unit = (
            Unit.objects
            .select_for_update()
            .get(pk=contract.unit_id)
        )

        if unit.status != UnitStatus.AVAILABLE:
            raise ValidationError(
                _("This unit is not available for activation "
                  "(current status: %(status)s).")
                % {"status": unit.get_status_display()}
            )

        # --- 4. Activate ---
        contract.status = ContractStatus.ACTIVE
        contract.save(update_fields=["status", "updated_at"])

        unit.status = UnitStatus.OCCUPIED
        unit.save(update_fields=["status", "updated_at"])

        return contract

    # -------------------------------------------------------------------------
    # Initial payment calculation
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_initial_payment(*, contract: RentalContract) -> Money:
        """
        Calculate the initial amount required for the contract.

        Formula:
            deposit + (monthly_rent * advance_rent_months)
        """
        if contract.advance_rent_months is None or contract.advance_rent_months < 1:
            raise ValidationError(_("Advance rent months must be at least 1."))

        if contract.deposit.currency != contract.monthly_rent.currency:
            raise ValidationError(
                _("Deposit and monthly rent must use the same currency.")
            )

        return contract.deposit + (
            contract.monthly_rent * contract.advance_rent_months
        )

    # -------------------------------------------------------------------------
    # Initial payment creation
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_initial_payment(
        *,
        contract: RentalContract,
        payment_method: str,
    ) -> Payment:
        """
        Create the initial charge and its pending payment.

        Idempotent: if an initial charge already exists for this contract,
        the existing pending payment is returned instead of creating a new one.

        The contract is not activated here — see `activate()`.
        """
        # --- 1. Validate payment_method ---
        if payment_method not in PaymentMethod.values:
            raise ValidationError(_("Invalid payment method."))

        # --- 2. Lock the contract ---
        contract = (
            RentalContract.objects
            .select_for_update()
            .get(pk=contract.pk)
        )

        if contract.status != ContractStatus.SIGNED:
            raise ValidationError(
                _("The initial payment can only be created for a signed contract.")
            )

        # --- 3. Idempotency: reuse existing initial charge ---
        existing_charge = (
            Charge.objects
            .filter(contract=contract, charge_type=ChargeType.INITIAL_PAYMENT)
            .first()
        )
        if existing_charge:
            existing_payment = existing_charge.payments.exclude(
                status=PaymentStatus.FAILED
            ).first()
            if existing_payment:
                return existing_payment

        # --- 4. Calculate amount ---
        amount = RentalContractService.calculate_initial_payment(contract=contract)

        if amount.amount <= 0:
            raise ValidationError(
                _("The initial payment amount must be greater than zero.")
            )

        # --- 5. Create the charge ---
        charge = Charge(
            contract=contract,
            charge_type=ChargeType.INITIAL_PAYMENT,
            amount=amount,
            due_date=contract.start_date,
            description=_(
                "Initial payment for rental contract %(contract)s."
            ) % {"contract": contract.contract_number},
        )
        charge.full_clean()
        charge.save()

        # --- 6. Create the payment ---
        payment = Payment(
            charge=charge,
            amount=amount,
            payment_method=payment_method,
            status=PaymentStatus.PENDING,
        )
        payment.full_clean()
        payment.save()

        return payment

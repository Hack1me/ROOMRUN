from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Unit
from rentals.models import RentalApplication
from rentals.models import RentalContract
from utils.enums import ApplicationStatus
from utils.enums import ContractStatus
from utils.enums import UnitStatus


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
        landlord_signature: str | None = None,
    ) -> RentalContract:
        """
        Create a rental contract after the landlord signs it.

        Contract starts in SIGNING. The unit remains AVAILABLE until
        the tenant signs (see `sign_by_tenant`).
        """
        # 1. Validate landlord signature
        if not landlord_signature or not landlord_signature.strip():
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
        tenant_signature: str,
    ) -> RentalContract:
        """Record the tenant's signature and activate the contract."""
        if not tenant_signature or not tenant_signature.strip():
            raise ValidationError(_("The tenant's signature is required."))

        contract = (
            RentalContract.objects
            .select_for_update()
            .select_related("unit")
            .get(pk=contract.pk)
        )

        if contract.status != ContractStatus.SIGNING:
            raise ValidationError(
                _("This contract is not awaiting the tenant's signature.")
            )

        contract.tenant_signature = tenant_signature
        contract.tenant_signed_at = timezone.now()
        contract.status = ContractStatus.ACTIVE
        contract.save(update_fields=[
            "tenant_signature",
            "tenant_signed_at",
            "status",
            "updated_at",
        ])

        # Mark the unit as occupied now that the contract is active.
        unit = Unit.objects.select_for_update().get(pk=contract.unit_id)
        unit.status = UnitStatus.OCCUPIED
        unit.save(update_fields=["status", "updated_at"])

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

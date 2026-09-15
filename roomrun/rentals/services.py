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

    @staticmethod
    @transaction.atomic
    def create(*, tenant, data: dict) -> RentalApplication:
        """
        Create a new rental application for a tenant.

        Forces the initial status to PENDING regardless of incoming data.
        """
        data.pop("tenant", None)
        data.pop("status", None)

        application = RentalApplication(
            tenant=tenant,
            status=ApplicationStatus.PENDING,
            **data,
        )
        application.full_clean()
        application.save()

        return application

    @staticmethod
    @transaction.atomic
    def _review(
        *,
        application: RentalApplication,
        reviewer,
        new_status: str,
    ) -> RentalApplication:
        """
        Internal helper: update the status and reviewer of an application.
        """
        if application.status != ApplicationStatus.PENDING:
            raise ValidationError(
                _("Only pending applications can be reviewed.")
            )
        application.status = new_status
        application.reviewed_by = reviewer
        application.reviewed_at = timezone.now()

        update_fields = ["status", "reviewed_by", "reviewed_at"]
        if hasattr(application, "updated_at"):
            update_fields.append("updated_at")

        application.save(update_fields=update_fields)

        return application

    @staticmethod
    @transaction.atomic
    def reject(*, application: RentalApplication, reviewer) -> RentalApplication:
        """Reject a rental application."""
        return RentalApplicationService._review(
            application=application,
            reviewer=reviewer,
            new_status=ApplicationStatus.REJECTED,
        )

    @staticmethod
    @transaction.atomic
    def cancel(*, application: RentalApplication) -> RentalApplication:
        """Cancel a rental application (e.g., by the tenant)."""
        application.status = ApplicationStatus.CANCELLED
        application.save(update_fields=["status", "updated_at"])
        return application


class RentalContractService:
    """Business logic related to rental contracts."""

    @staticmethod
    @transaction.atomic
    def create(
        *,
        tenant,
        unit,
        data: dict,
        application: RentalApplication | None = None,
        reviewer=None,
    ) -> RentalContract:
        """
        Create a rental contract.

        Locks the unit and (optional) application to prevent concurrent
        contract creation. Validates business rules and updates the
        application status if provided.

        Raises:
            ValidationError: If any business rule is violated.
        """
        # -----------------------------------------------------------------
        # 1. Sanitize incoming data
        # -----------------------------------------------------------------
        data = dict(data)
        data.pop("tenant", None)
        data.pop("unit", None)
        data.pop("application", None)
        data.pop("status", None)

        # -----------------------------------------------------------------
        # 2. Lock and validate the unit
        # -----------------------------------------------------------------
        unit = Unit.objects.select_for_update().get(pk=unit.pk)

        if unit.status != UnitStatus.AVAILABLE:
            raise ValidationError(_("This unit is no longer available."))

        # Prevent two active contracts on the same unit
        has_active_contract = RentalContract.objects.filter(
            unit=unit,
            status=ContractStatus.ACTIVE,
        ).exists()
        if has_active_contract:
            raise ValidationError(
                _("This unit already has an active contract.")
            )

        # -----------------------------------------------------------------
        # 3. Lock and validate the application (if provided)
        # -----------------------------------------------------------------
        if application:
            if reviewer is None:
                raise ValidationError(
                    _("A reviewer is required when approving an application.")
                )

            application = (
                RentalApplication.objects
                .select_for_update()
                .get(pk=application.pk)
            )

            if application.status != ApplicationStatus.PENDING:
                raise ValidationError(
                    _("This application has already been reviewed.")
                )
            if application.tenant_id != tenant.pk:
                raise ValidationError(
                    _("The application tenant does not match the contract tenant.")
                )
            if application.unit_id != unit.pk:
                raise ValidationError(
                    _("The application unit does not match the contract unit.")
                )
            if hasattr(application, "rental_contract"):
                raise ValidationError(
                    _("This application already has a contract.")
                )

        # -----------------------------------------------------------------
        # 4. Create the contract
        # -----------------------------------------------------------------
        contract = RentalContract(
            tenant=tenant,
            unit=unit,
            application=application,
            status=ContractStatus.ACTIVE,
            **data,
        )
        contract.full_clean()
        contract.save()

        # -----------------------------------------------------------------
        # 5. Mark the application as approved
        # -----------------------------------------------------------------
        if application:
            application.status = ApplicationStatus.APPROVED
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

        return contract

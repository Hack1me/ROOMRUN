from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rentals.models import RentalApplication
from utils.enums import ApplicationStatus


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
    def approve(*, application: RentalApplication, reviewer) -> RentalApplication:
        """Approve a rental application."""
        return RentalApplicationService._review(
            application=application,
            reviewer=reviewer,
            new_status=ApplicationStatus.APPROVED,
        )

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

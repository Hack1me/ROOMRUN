from core.models import BaseModel
from core.utils import safe_reverse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from properties.models import Unit
from users.models import Tenant
from utils.enums import ApplicationStatus
from utils.enums import ContractStatus
from utils.enums import UnitStatus


# RENTAL APPLICATION
class RentalApplication(BaseModel):
    """
    Represents a rental application submitted by a tenant for a specific unit.
    Each application has a status and an auto-generated unique number.
    """

    reference_field = "application_number"
    reference_prefix = "APP"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="rental_applications",
        verbose_name=_("Tenant"),
        help_text=_("The tenant submitting the application."),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="rental_applications",
        verbose_name=_("Unit"),
        help_text=_("The unit being applied for."),
    )

    application_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Application number"),
        help_text=_("Auto-generated unique identifier for the application."),
        # Generation logic must be provided via a signals.py
    )

    message = models.TextField(
        blank=True,
        verbose_name=_("Message"),
        help_text=_("Optional message provided by the tenant."),
    )

    desired_duration = models.PositiveIntegerField(
    null=True,
    blank=True,
    verbose_name=_("Desired duration"),
    help_text=_("Desired rental duration in months."),
    )

    occupants_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Number of occupants"),
    )

    desired_move_in_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Desired move-in date"),
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the rental application."),
    )

    applied_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Applied at"),
        help_text=_("Time at which the application was submitted."),
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed at"),
        help_text=_("Time at which the application was reviewed."),
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_rental_applications",
        verbose_name=_("Reviewed by"),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "rental_applications"
        ordering = ["-created_at"]  # Use BaseModel's created_at
        verbose_name = _("Rental application")
        verbose_name_plural = _("Rental applications")

        indexes = [
            models.Index(fields=["tenant"], name="rental_app_tenant_idx"),
            models.Index(fields=["unit"], name="rental_app_unit_idx"),
            models.Index(fields=["status"], name="rental_app_status_idx"),
            models.Index(fields=["reviewed_at"], name="rental_app_reviewed_at_idx"),
        ]

        # prevent duplicate applications from the same tenant for the same unit
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "unit"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_application_per_tenant_unit",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the application number as string representation."""
        return self.application_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the application detail view."""
        return safe_reverse("rentals:rental-application-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validation: a tenant cannot have an approved application
        for the same unit.
        """
        super().clean()
        if self.status == ApplicationStatus.APPROVED:
            existing = RentalApplication.objects.filter(
                tenant=self.tenant,
                unit=self.unit,
                status=ApplicationStatus.APPROVED,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    _("This tenant already has an approved application for this unit.")
                )

        if self.status != ApplicationStatus.PENDING and not self.reviewed_at:
            raise ValidationError(
                _("Reviewed at is required once an application is decided.")
            )


# RENTAL CONTRACT
class RentalContract(BaseModel):
    """
    Represents a rental contract between a tenant and a unit.
    Each contract has a unique number and a status indicating its lifecycle.
    """

    reference_field = "contract_number"
    reference_prefix = "CNT"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,  # Prevents deletion if contract exists
        related_name="rental_contracts",
        verbose_name=_("Tenant"),
        help_text=_("The tenant who signs this contract."),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="rental_contracts",
        verbose_name=_("Unit"),
        help_text=_("The unit being rented under this contract."),
    )

    application = models.OneToOneField(
        RentalApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rental_contract",
        verbose_name=_("Rental application"),
        help_text=_("Approved application that resulted in this contract."),
    )

    contract_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Contract number"),
        help_text=_("Auto-generated unique identifier for the contract."),
        # Generation logic must be added via a signals.py
    )

    start_date = models.DateField(
        verbose_name=_("Start date"),
        help_text=_("The date when the contract becomes effective."),
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("End date"),
        help_text=_("Leave empty for an open-ended contract."),
    )

    monthly_rent = MoneyField(
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
        verbose_name=_("Monthly rent"),
        help_text=_("Monthly rental amount in the local currency."),
    )

    deposit = MoneyField(
        max_digits=12,
        decimal_places=2,
        default=0,
        default_currency="XAF",
        verbose_name=_("Security deposit"),
        help_text=_("Security deposit required at contract signing."),
    )

    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current lifecycle status of the contract."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "rental_contracts"
        ordering = ["-created_at"]
        verbose_name = _("Rental contract")
        verbose_name_plural = _("Rental contracts")

        indexes = [
            models.Index(fields=["tenant"], name="rental_contract_tenant_idx"),
            models.Index(fields=["unit"], name="rental_contract_unit_idx"),
            models.Index(fields=["status"], name="rental_contract_status_idx"),
            models.Index(fields=["start_date"], name="rental_contract_start_idx"),
        ]

        constraints = [
            # A unit can have only one active contract at a time.
            models.UniqueConstraint(
                fields=["unit"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_contract_per_unit",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the contract number as string representation."""
        return self.contract_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the contract detail view."""
        return safe_reverse("rentals:rental-contract-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. End date must be after start date (if provided).
        2. A tenant cannot have another active contract for the same unit.
        """
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError(_("End date must be after the start date."))

        super().clean()
        if self.application and (
            self.application.tenant_id != self.tenant_id
            or self.application.unit_id != self.unit_id
        ):
            raise ValidationError(
                _("The linked application must concern the same tenant and unit.")
            )

        if self.status == ContractStatus.ACTIVE:
            existing = RentalContract.objects.filter(
                unit=self.unit,
                status=ContractStatus.ACTIVE,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(_("This unit already has an active contract."))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == ContractStatus.ACTIVE:
            Unit.objects.filter(pk=self.unit_id).update(status=UnitStatus.OCCUPIED)
        elif (
            not RentalContract.objects.filter(
                unit_id=self.unit_id, status=ContractStatus.ACTIVE
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            Unit.objects.filter(pk=self.unit_id, status=UnitStatus.OCCUPIED).update(
                status=UnitStatus.AVAILABLE
            )

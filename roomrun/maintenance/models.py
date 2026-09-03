from core.models import BaseModel
from core.utils import safe_reverse
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Unit
from users.models import MaintenanceAgent
from users.models import Tenant
from utils.enums import Priority
from utils.enums import RequestStatus
from utils.enums import TaskStatus


# MAINTENANCE REQUEST
class MaintenanceRequest(BaseModel):
    """
    Represents a maintenance request submitted for a rental unit.
    Each request has a unique number and tracks its lifecycle status.
    """

    reference_field = "request_number"
    reference_prefix = "MNT"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    request_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Request number"),
        help_text=_("Auto-generated unique identifier for the maintenance request."),
        # Generation logic must be added via a signals.py
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,  # Prevents deletion if requests exist
        related_name="maintenance_requests",
        verbose_name=_("Tenant"),
        help_text=_("The tenant who submitted the maintenance request."),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
        verbose_name=_("Unit"),
        help_text=_("The unit where the maintenance issue is located."),
    )

    title = models.CharField(
        max_length=150,
        verbose_name=_("Title"),
        help_text=_("Brief summary of the maintenance issue."),
    )

    description = models.TextField(
        verbose_name=_("Description"),
        help_text=_("Detailed description of the maintenance issue."),
        blank=False,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name=_("Priority"),
        help_text=_("Priority level of the maintenance request."),
    )

    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        verbose_name=_("Status"),
        help_text=_("Current status of the maintenance request."),
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Resolved at"),
        help_text=_("Timestamp when the request was resolved."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "maintenance_requests"
        ordering = ["-created_at"]
        verbose_name = _("Maintenance request")
        verbose_name_plural = _("Maintenance requests")

        indexes = [
            models.Index(fields=["tenant"], name="maintenance_req_tenant_idx"),
            models.Index(fields=["unit"], name="maintenance_req_unit_idx"),
            models.Index(fields=["status"], name="maintenance_req_status_idx"),
            models.Index(fields=["priority"], name="maintenance_req_priority_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the request number as string representation."""
        return self.request_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the maintenance request detail view."""
        return safe_reverse("maintenance:request-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. When status is RESOLVED, resolved_at must be set.
        2. resolved_at cannot be in the future.
        """
        super().clean()
        if self.tenant_id and self.unit_id:
            from rentals.models import RentalContract  # noqa: PLC0415
            from utils.enums import ContractStatus  # noqa: PLC0415

            is_occupant = RentalContract.objects.filter(
                tenant_id=self.tenant_id,
                unit_id=self.unit_id,
                status=ContractStatus.ACTIVE,
            ).exists()
            if not is_occupant:
                raise ValidationError(
                    _(
                        "A maintenance request can only concern the tenant's "
                        "active unit."
                    )
                )

        if self.status == RequestStatus.RESOLVED:
            if not self.resolved_at:
                raise ValidationError(
                    _("Resolved at date is required when status is RESOLVED.")
                )
            if self.resolved_at > timezone.now():
                raise ValidationError(_("Resolved at date cannot be in the future."))

        # When status is not RESOLVED, resolved_at should be null
        if self.status != RequestStatus.RESOLVED and self.resolved_at:
            raise ValidationError(
                _("Resolved at should only be set when status is RESOLVED.")
            )


class MaintenanceRequestAttachment(BaseModel):
    """File or photo supplied as evidence for a maintenance request."""

    maintenance_request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("Maintenance request"),
    )
    file = models.FileField(upload_to="maintenance/attachments/")
    caption = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.caption or self.file.name


# TASK
class Task(BaseModel):
    """
    Represents a maintenance task assigned to a maintenance agent.
    Each task has a unique number and tracks its lifecycle from scheduling
    through to completion.
    """

    reference_field = "task_number"
    reference_prefix = "TSK"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    task_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Task number"),
        help_text=_("Auto-generated unique identifier for the task."),
        # Generation logic must be added via a signals.py
    )

    maintenance_request = models.ForeignKey(
        "maintenance.MaintenanceRequest",
        on_delete=models.PROTECT,  # Prevents deletion if tasks exist
        related_name="tasks",
        verbose_name=_("Maintenance request"),
        help_text=_("The maintenance request this task belongs to."),
    )

    maintenance_agent = models.ForeignKey(
        MaintenanceAgent,
        on_delete=models.PROTECT,
        related_name="tasks",
        verbose_name=_("Maintenance agent"),
        help_text=_("The agent assigned to perform this task."),
    )

    title = models.CharField(
        max_length=150,
        verbose_name=_("Title"),
        help_text=_("Brief summary of the task."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Detailed description of the work to be performed."),
    )

    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the task."),
    )

    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Scheduled at"),
        help_text=_("Date and time when the task is scheduled to start."),
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Started at"),
        help_text=_("Date and time when the task actually started."),
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed at"),
        help_text=_("Date and time when the task was completed."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "maintenance_tasks"
        ordering = ["-created_at"]
        verbose_name = _("Maintenance task")
        verbose_name_plural = _("Maintenance tasks")

        indexes = [
            models.Index(fields=["maintenance_request"], name="task_request_idx"),
            models.Index(fields=["maintenance_agent"], name="task_agent_idx"),
            models.Index(fields=["status"], name="task_status_idx"),
            models.Index(fields=["scheduled_at"], name="task_scheduled_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the task number as string representation."""
        return self.task_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the task detail view."""
        return safe_reverse("maintenance:task-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. Timestamps must be in chronological order.
        2. Status must be consistent with timestamps.
        """
        super().clean()
        # Validate chronological order
        if self.scheduled_at and self.started_at:
            if self.started_at < self.scheduled_at:
                raise ValidationError(_("Started at cannot be before scheduled at."))

        if self.started_at and self.completed_at:
            if self.completed_at < self.started_at:
                raise ValidationError(_("Completed at cannot be before started at."))

        # Status validation
        if self.status == TaskStatus.COMPLETED and not self.completed_at:
            raise ValidationError(
                _("Completed at is required when status is COMPLETED.")
            )

        if self.status == TaskStatus.IN_PROGRESS and not self.started_at:
            raise ValidationError(
                _("Started at is required when status is IN_PROGRESS.")
            )

        # Cleanup: if status is not COMPLETED, completed_at should be null
        if self.status != TaskStatus.COMPLETED and self.completed_at:
            raise ValidationError(
                _("Completed at should only be set when status is COMPLETED.")
            )

        if self.status != TaskStatus.IN_PROGRESS and self.started_at:
            # Allow started_at to be set even if status is not IN_PROGRESS
            # (e.g., scheduled tasks may have a start time)
            pass

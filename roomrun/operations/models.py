from core.models import BaseModel
from core.utils import safe_reverse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Building
from users.models import Tenant
from utils.enums import CleaningStatus
from utils.enums import InvitationStatus
from utils.enums import UserRole


class CleaningSchedule(BaseModel):
    """
    Represents a scheduled cleaning operation for a building.
    This schedule is visible to tenants and does not include employee
    assignments (those are handled in CleaningCalendar).
    """

    reference_field = "schedule_number"
    reference_prefix = "CLS"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    schedule_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Schedule number"),
        help_text=_("Auto-generated unique identifier for the cleaning schedule."),
        # Generation logic must be added via a signals.py
    )

    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,  # Prevents deletion if schedules exist
        related_name="cleaning_schedules",
        verbose_name=_("Building"),
        help_text=_("The building to be cleaned."),
    )

    scheduled_date = models.DateField(
        verbose_name=_("Scheduled date"),
        help_text=_("The date when the cleaning is scheduled."),
    )

    start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Start time"),
        help_text=_("The time the cleaning is scheduled to start."),
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("End time"),
        help_text=_("The time the cleaning is scheduled to end."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional details about the cleaning task."),
    )

    status = models.CharField(
        max_length=20,
        choices=CleaningStatus.choices,
        default=CleaningStatus.SCHEDULED,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the cleaning schedule."),
    )

    assigned_Tenant = models.ManyToManyField(  # noqa: N815
        Tenant,
        blank=True,
        related_name="cleaning_schedules",
        verbose_name=_("Assigned employees"),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "cleaning_schedules"
        ordering = ["scheduled_date", "start_time"]
        verbose_name = _("Cleaning schedule")
        verbose_name_plural = _("Cleaning schedules")

        indexes = [
            models.Index(fields=["building"], name="cleaning_schedule_building_idx"),
            models.Index(fields=["scheduled_date"], name="cleaning_schedule_date_idx"),
            models.Index(fields=["status"], name="cleaning_schedule_status_idx"),
            # Composite index for common filtering on building and date
            models.Index(
                fields=["building", "scheduled_date"],
                name="cleaning_building_date_idx",
            ),
        ]

        # Prevent duplicate schedules for the same building on the same date
        constraints = [
            models.UniqueConstraint(
                fields=["building", "scheduled_date"],
                condition=Q(status=CleaningStatus.SCHEDULED),
                name="unique_scheduled_cleaning_per_building_date",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the schedule number as string representation."""
        return self.schedule_number

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the cleaning schedule detail view."""
        return safe_reverse("operations:cleaning-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. End time must be after start time (if both provided).
        2. Scheduled date cannot be in the past.
        """
        super().clean()
        # Validate time order
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError(_("End time must be after start time."))

        # Validate scheduled date is not in the past
        if (
            self.status == CleaningStatus.SCHEDULED
            and self.scheduled_date
            and self.scheduled_date < timezone.now().date()
        ):
            raise ValidationError(_("Scheduled date cannot be in the past."))


class UserInvitation(BaseModel):
    """
    Represents an invitation sent by a user (e.g., a landlord) to invite
    someone to join the platform with a specific role.

    The invitation is validated via a hashed token, which is never stored
    in plain text. Tokens expire after `expires_at`.
    """

    # Signal hints for auto-generated invitation number
    reference_field = "invitation_number"
    reference_prefix = "INV"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    email = models.EmailField(
        db_index=True,
        verbose_name=_("Email"),
        help_text=_("Email address of the invited person."),
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_invitations",
        verbose_name=_("Invited by"),
        help_text=_("The user who sent the invitation."),
    )

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        db_index=True,
        verbose_name=_("Role"),
        help_text=_("The role being offered to the invited person."),
    )

    invitation_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Invitation number"),
        help_text=_("Auto-generated unique identifier (set via signals)."),
    )

    token_hash = models.CharField(
        max_length=128,
        unique=True,
        verbose_name=_("Token hash"),
        help_text=_("SHA-256 (or similar) hash of the invitation token."),
    )

    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the invitation."),
    )

    expires_at = models.DateTimeField(
        verbose_name=_("Expires at"),
        help_text=_("The date and time when the invitation expires."),
    )

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Accepted at"),
        help_text=_("The date and time when the invitation was accepted."),
    )

    # -------------------------------------------------------------------------
    # Meta
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "user_invitations"
        ordering = ["-created_at"]
        verbose_name = _("User invitation")
        verbose_name_plural = _("User invitations")

        indexes = [
            models.Index(
                fields=["email", "status"],
                name="usr_inv_email_status_idx",
            ),
            models.Index(
                fields=["invited_by", "role"],
                name="usr_inv_sender_role_idx",
            ),
            models.Index(
                fields=["expires_at"],
                name="usr_inv_expires_idx",
            ),
        ]

        constraints = [
            # Prevent duplicate pending invitations for the same email, role,
            # and inviter.
            models.UniqueConstraint(
                fields=["email", "invited_by", "role"],
                condition=models.Q(status=InvitationStatus.PENDING),
                name="unique_pending_invitation_per_sender_role",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        return str(self.invitation_number)

    @property
    def is_expired(self) -> bool:
        """Return whether the invitation has expired."""
        return timezone.now() >= self.expires_at

    @property
    def can_accept(self) -> bool:
        """Return whether the invitation can still be accepted."""
        return self.status == InvitationStatus.PENDING and not self.is_expired

    @property
    def is_accepted(self) -> bool:
        """Return whether the invitation has been accepted."""
        return self.status == InvitationStatus.ACCEPTED

    @property
    def is_pending(self) -> bool:
        """Return whether the invitation is still pending."""
        return self.status == InvitationStatus.PENDING

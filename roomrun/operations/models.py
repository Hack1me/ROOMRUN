from core.models import BaseModel
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Building
from utils.enums import CleaningStatus


class CleaningSchedule(BaseModel):
    """
    Represents a scheduled cleaning operation for a building.
    This schedule is visible to tenants and does not include employee
    assignments (those are handled in CleaningCalendar).
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    schedule_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Schedule number"),
        help_text=_("Auto-generated unique identifier for the cleaning schedule."),
        # 🔧 Generation logic must be added via a signal or overridden save()
    )

    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,          # Prevents deletion if schedules exist
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
                name="cleaning_schedule_building_date_idx",
            ),
        ]

        # Optional: Prevent duplicate schedules for the same building on the same date
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
        return reverse("operations:cleaning-schedule-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. End time must be after start time (if both provided).
        2. Scheduled date cannot be in the past.
        """
        # Validate time order
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError(
                    _("End time must be after start time.")
                )

        # Validate scheduled date is not in the past
        if self.scheduled_date and self.scheduled_date < timezone.now().date():
            raise ValidationError(
                _("Scheduled date cannot be in the past.")
            )

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

"""
Abstract base model inherited by concrete models.

Provides:
- UUID primary key
- creation and update timestamps
- audit information
- soft deletion
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import AllObjectsManager
from .managers import SoftDeleteManager


class BaseModel(models.Model):
    """
    Abstract base model shared by ROOMRUN domain models.
    """

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        null=False,
        verbose_name=_("ID"),
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
    )

    # -------------------------------------------------------------------------
    # Audit
    # -------------------------------------------------------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name=_("Created by"),
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name=_("Updated by"),
    )

    # -------------------------------------------------------------------------
    # Soft deletion
    # -------------------------------------------------------------------------

    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is deleted"),
        help_text=_("Indicates whether this record has been soft-deleted."),
    )

    # -------------------------------------------------------------------------
    # Managers
    # -------------------------------------------------------------------------

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()
    reference_field: str | None = None
    reference_prefix: str | None = None

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.pk})"

    def save(self, *args, **kwargs) -> None:
        """Validate domain rules and retain status transitions when applicable."""
        if self.reference_field and self.reference_prefix:
            from utils.helpers import assign_reference_identifier  # noqa: PLC0415

            assign_reference_identifier(
                self,
                field=self.reference_field,
                prefix=self.reference_prefix,
            )

        previous_status = None
        if not self._state.adding and any(
            field.name == "status" for field in self._meta.fields
        ):
            previous_status = (
                self.__class__.all_objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        self.full_clean()
        super().save(*args, **kwargs)

        if previous_status is not None and previous_status != self.status:
            StatusHistory.objects.create(
                content_object=self,
                previous_status=previous_status,
                status=self.status,
                changed_by=self.updated_by,
            )

    def soft_delete(self, user=None) -> None:
        """Soft-delete this instance and record the responsible user."""
        self.is_deleted = True
        self.updated_by = user
        self.save(
            update_fields=[
                "is_deleted",
                "updated_by",
                "updated_at",
            ],
        )

    def restore(self, user=None) -> None:
        """Restore this instance and record the responsible user."""
        self.is_deleted = False
        self.updated_by = user
        self.save(
            update_fields=[
                "is_deleted",
                "updated_by",
                "updated_at",
            ],
        )


class ReadableModelMixin(models.Model):
    """Reusable read-state fields and behaviour for user-facing content."""

    is_read = models.BooleanField(default=False, db_index=True, verbose_name=_("Read"))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Read at"))

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.is_read and not self.read_at:
            raise ValidationError(
                _("Read at must be set when the item is marked as read.")
            )
        if not self.is_read and self.read_at:
            raise ValidationError(
                _("Read at should be empty when the item is not read.")
            )
        if self.read_at and self.read_at > timezone.now():
            raise ValidationError(_("Read at cannot be in the future."))

    def mark_as_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])

    def mark_as_unread(self) -> None:
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=["is_read", "read_at", "updated_at"])

    @property
    def is_unread(self) -> bool:
        return not self.is_read


class StatusHistory(models.Model):
    """Audit trail of status changes for every ROOMRUN domain model."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    previous_status = models.CharField(max_length=30)
    status = models.CharField(max_length=30)
    changed_at = models.DateTimeField(default=timezone.now, db_index=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
    )

    class Meta:
        ordering = ["-changed_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self) -> str:
        return f"{self.content_object}: {self.previous_status} → {self.status}"


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
from django.db import models
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

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.pk})"

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

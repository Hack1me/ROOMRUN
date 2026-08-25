""""
─────────────────────
Abstract base model inherited by every concrete model in the project.
Provides: UUID PK · timestamps · audit (created_by / updated_by) · soft-delete.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# from roomrun.core.managers import AllObjectsManager  # noqa: ERA001
# from roomrun.core.managers import SoftDeleteManager  # noqa: ERA001

if TYPE_CHECKING:
    from roomrun.users.models import User


class BaseModel(models.Model):
    """
        Abstract base model with UUID primary key, timestamps, audit fields, and soft-delete.
        All concrete models should inherit from this to ensure consistency across the platform.
    """  # noqa: E501

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created at"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name=_("Created by"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name=_("Updated at"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name=_("Updated by"),
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Is deleted"),
        help_text=_("Soft-delete flag. Deactivated records are excluded from default queries."),
    )

    """
        #Managers
        objects = SoftDeleteManager()
        all_objects = AllObjectsManager()
    """

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.pk})"

    def soft_delete(self, user: User | None = None) -> None:
        """Deactivate this instance and record who deleted it."""
        self.is_deleted = True
        self.updated_by = user
        self.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    def restore(self, user: User | None = None) -> None:
        """Reactivate a soft-deleted instance."""
        self.is_deleted = False
        self.updated_by = user
        self.save(update_fields=["is_deleted", "updated_by", "updated_at"])

from __future__ import annotations

from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet providing soft-delete operations."""

    def delete(self):
        """
        Soft-delete all objects in the queryset.

        Returns:
            Number of updated objects and field update details.
        """
        return self.update(is_deleted=True)

    def hard_delete(self):
        """
        Permanently delete all objects in the queryset.

        Returns:
            Deletion details returned by Django.
        """
        return super().delete()

    def restore(self):
        """
        Restore all soft-deleted objects in the queryset.

        Returns:
            Number of restored objects and field update details.
        """
        return self.update(is_deleted=False)


class SoftDeleteManager(models.Manager):
    """
    Default manager for models supporting soft deletion.

    Only non-deleted objects are returned.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """
    Manager returning both active and soft-deleted objects.
    """

    def get_queryset(self):
        return super().get_queryset()

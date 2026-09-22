from __future__ import annotations

from core.managers import SoftDeleteQuerySet
from django.db import models


class LandlordRentalQuerySet(SoftDeleteQuerySet):
    """QuerySet filtered to objects accessible by a specific landlord."""

    def for_landlord(self, landlord):
        return self.filter(unit__building__property_ref__landlord=landlord)


class LandlordRentalManager(models.Manager):
    """Manager scoped to a specific landlord's rental objects."""

    def get_queryset(self):
        return LandlordRentalQuerySet(self.model, using=self._db)

    def for_landlord(self, landlord):
        return self.get_queryset().for_landlord(landlord)

# enums.py
from django.db import models
from django.utils.translation import gettext_lazy as _


class EmployeeStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    SUSPENDED = "SUSPENDED", _("Suspended")


class GuardShift(models.TextChoices):
    DAY = "DAY", _("Day")
    NIGHT = "NIGHT", _("Night")
    ROTATING = "ROTATING", _("Rotating")

class PropertyStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION", _("Under construction")

class UnitStatus(models.TextChoices):
    """
    Defines the possible occupancy statuses for a unit.
    Used as choices for the `status` field.
    """
    AVAILABLE = "AVAILABLE", _("Available")
    OCCUPIED = "OCCUPIED", _("Occupied")
    RESERVED = "RESERVED", _("Reserved")
    MAINTENANCE = "MAINTENANCE", _("Under maintenance")
    INACTIVE = "INACTIVE", _("Inactive")


class UnitType(models.TextChoices):
    """
    Defines the possible types of rental units.
    Used as choices for the `unit_type` field.
    """
    STUDIO = "STUDIO", _("Studio")
    APARTMENT = "APARTMENT", _("Apartment")
    OFFICE = "OFFICE", _("Office")
    RETAIL = "RETAIL", _("Retail")
    WAREHOUSE = "WAREHOUSE", _("Warehouse")
    PENTHOUSE = "PENTHOUSE", _("Penthouse")

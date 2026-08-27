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


class ApplicationStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")
    CANCELLED = "CANCELLED", _("Cancelled")

class ContractStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        COMPLETED = "COMPLETED", _("Completed")
        TERMINATED = "TERMINATED", _("Terminated")
        CANCELLED = "CANCELLED", _("Cancelled")


class ChargeType(models.TextChoices):
    """
    Defines the types of financial charges that can be applied to a rental contract.
    """
    RENT = "RENT", _("Rent")
    ELECTRICITY = "ELECTRICITY", _("Electricity")
    WATER = "WATER", _("Water")
    GAS = "GAS", _("Gas")
    INTERNET = "INTERNET", _("Internet")
    MAINTENANCE_FEE = "MAINTENANCE_FEE", _("Maintenance fee")
    TRASH = "TRASH", _("Trash collection")
    PARKING = "PARKING", _("Parking")
    LATE_FEE = "LATE_FEE", _("Late fee")
    OTHER = "OTHER", _("Other")


class ChargeStatus(models.TextChoices):
    """
    Defines the lifecycle status of a financial charge.
    Ordered to reflect the natural flow: pending → paid / overdue / cancelled.
    """
    PENDING = "PENDING", _("Pending")
    PARTIAL = "PARTIAL", _("Partially paid")
    PAID = "PAID", _("Paid")
    OVERDUE = "OVERDUE", _("Overdue")
    CANCELLED = "CANCELLED", _("Cancelled")

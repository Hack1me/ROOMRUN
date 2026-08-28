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


class PaymentMethod(models.TextChoices):
    """
    Defines the methods available for making payments.
    """

    CASH = "CASH", _("Cash")
    MOBILE_MONEY = "MOBILE_MONEY", _("Mobile Money")
    BANK_TRANSFER = "BANK_TRANSFER", _("Bank transfer")
    CREDIT_CARD = "CREDIT_CARD", _("Credit card")
    PAYPAL = "PAYPAL", _("PayPal")
    CHECK = "CHECK", _("Check")
    OTHER = "OTHER", _("Other")


class PaymentStatus(models.TextChoices):
    """
    Defines the lifecycle status of a payment.
    """

    PENDING = "PENDING", _("Pending")
    COMPLETED = "COMPLETED", _("Completed")
    FAILED = "FAILED", _("Failed")
    REFUNDED = "REFUNDED", _("Refunded")
    CANCELLED = "CANCELLED", _("Cancelled")


class Priority(models.TextChoices):
    """
    Defines the urgency levels for maintenance requests.
    Used to prioritize and allocate resources accordingly.
    """

    LOW = "LOW", _("Low")
    MEDIUM = "MEDIUM", _("Medium")
    HIGH = "HIGH", _("High")
    URGENT = "URGENT", _("Urgent")


class RequestStatus(models.TextChoices):
    """
    Defines the lifecycle status of a maintenance request.
    Tracks the progress from submission to resolution or cancellation.
    """

    PENDING = "PENDING", _("Pending")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    RESOLVED = "RESOLVED", _("Resolved")
    CANCELLED = "CANCELLED", _("Cancelled")


class TaskStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    ASSIGNED = "ASSIGNED", _("Assigned")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELLED = "CANCELLED", _("Cancelled")


class CleaningStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", _("Scheduled")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELLED = "CANCELLED", _("Cancelled")


class AnnouncementStatus(models.TextChoices):
    ARCHIVED = "ARCHIVED", _("Archived")
    EXPIRED = "EXPIRED", _("Expired")
    DRAFT = "DRAFT", _("Draft")
    SCHEDULED = "SCHEDULED", _("Scheduled")
    PUBLISHED = "PUBLISHED", _("Published")


class AnnouncementTarget(models.TextChoices):
    ALL_TENANTS = "ALL_TENANTS", _("All tenants")
    BUILDING = "BUILDING", _("Building")
    UNIT = "UNIT", _("Unit")


class NotificationType(models.TextChoices):
    PAYMENT = "PAYMENT", _("Payment")
    RENT_REMINDER = "RENT_REMINDER", _("Rent reminder")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")
    TASK = "TASK", _("Task")
    ANNOUNCEMENT = "ANNOUNCEMENT", _("Announcement")
    SYSTEM = "SYSTEM", _("System")

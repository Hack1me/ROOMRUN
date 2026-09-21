from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _


class EmployeeStatus(models.TextChoices):
    """
    Defines the possible employment statuses for an employee.
    Used to track whether an employee is actively working, inactive, or suspended.
    """

    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    SUSPENDED = "SUSPENDED", _("Suspended")


class GuardShift(models.TextChoices):
    """
    Defines the possible shift types for security guards.
    Used to schedule and manage guard shifts across different times of day.
    """

    DAY = "DAY", _("Day")
    NIGHT = "NIGHT", _("Night")
    ROTATING = "ROTATING", _("Rotating")


class PropertyType(models.TextChoices):
    """
    Defines the possible types of a property.
    Used as choices for the `property_type` field.
    """

    RESIDENTIAL = "RESIDENTIAL", _("Residential")
    COMMERCIAL = "COMMERCIAL", _("Commercial")
    MIXED = "MIXED", _("Mixed use")


class PropertyStatus(models.TextChoices):
    """
    Defines the possible operational statuses for a property.
    Indicates if property is actively managed, inactive, or under construction.
    """

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
    """
    Defines the lifecycle status of a rental application.
    Tracks the progress from submission through approval, rejection, or cancellation.
    """

    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")
    CANCELLED = "CANCELLED", _("Cancelled")


class ContractStatus(models.TextChoices):
    """
    Defines the lifecycle status of a rental contract.
    Indicates the current state of a lease agreement between landlord and tenant.
    """
    SIGNING = "SIGNING", _("Signing")
    SIGNED = "SIGNED", _("Signed")
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    TERMINATED = "TERMINATED", _("Terminated")
    CANCELLED = "CANCELLED", _("Cancelled")


class ChargeType(models.TextChoices):
    """
    Defines the types of financial charges that can be applied to a rental contract.
    """

    RENT = "RENT", _("Rent")
    INITIAL_PAYMENT = "INITIAL_PAYMENT", _("Initial payment")
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
    """
    Defines the lifecycle status of a work task.
    Tracks progression from creation through assignment, execution, completion,
    or cancellation.
    """

    PENDING = "PENDING", _("Pending")
    ASSIGNED = "ASSIGNED", _("Assigned")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELLED = "CANCELLED", _("Cancelled")


class CleaningStatus(models.TextChoices):
    """
    Defines the lifecycle status of a cleaning operation.
    Tracks cleaning tasks from scheduling through completion or cancellation.
    """

    SCHEDULED = "SCHEDULED", _("Scheduled")
    IN_PROGRESS = "IN_PROGRESS", _("In progress")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELLED = "CANCELLED", _("Cancelled")


class AnnouncementStatus(models.TextChoices):
    """
    Defines the lifecycle status of an announcement.
    Tracks from draft through scheduling, publishing, expiration or archival.
    """

    ARCHIVED = "ARCHIVED", _("Archived")
    EXPIRED = "EXPIRED", _("Expired")
    DRAFT = "DRAFT", _("Draft")
    SCHEDULED = "SCHEDULED", _("Scheduled")
    PUBLISHED = "PUBLISHED", _("Published")


class AnnouncementTarget(models.TextChoices):
    """
    Defines the scope/target audience for an announcement.
    Used to control who receives a particular announcement.
    """

    ALL_TENANTS = "ALL_TENANTS", _("All tenants")
    BUILDING = "BUILDING", _("Building")
    UNIT = "UNIT", _("Unit")


class NotificationType(models.TextChoices):
    """
    Defines the categories of notifications that can be sent to users.
    Used to categorize and filter notifications by type.
    """

    PAYMENT = "PAYMENT", _("Payment")
    RENT_REMINDER = "RENT_REMINDER", _("Rent reminder")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")
    TASK = "TASK", _("Task")
    ANNOUNCEMENT = "ANNOUNCEMENT", _("Announcement")
    SYSTEM = "SYSTEM", _("System")


class UserStatus(models.TextChoices):
    """
    Defines the possible account statuses for a user.
    Used to track user account lifecycle: active, inactive, or suspended.
    """

    ACTIVE = "ACTIVE", _("Actif")  # Normal active account
    INACTIVE = "INACTIVE", _("Inactif")  # Disabled but not suspended
    SUSPENDED = "SUSPENDED", _("Suspendu")  # Temporarily blocked

class UserRole(models.TextChoices):
    """
    Defines the possible dashboard roles for a user.
    Values are stored as strings and can be used directly as Django choices.
    """
    LANDLORD = "landlord"
    TENANT = "tenant"
    GUARD = "guard"
    MAINTENANCE = "maintenance"
    EMPLOYEE = "employee"
    USER = "user"


class OtpPurpose(models.TextChoices):
    """Operations for which a one-time verification code can be issued."""

    SIGNUP = "signup", _("Sign up")
    LOGIN = "login", _("Sign in")
    PASSWORD_RESET = "password_reset", _("Password reset")


class InvitationStatus(models.TextChoices):
    """
    Defines the lifecycle status of an invitation.
    Tracks invitations from pending through acceptance, expiration, or rejection.
    """

    PENDING = "PENDING", _("Pending")
    ACCEPTED = "ACCEPTED", _("Accepted")
    EXPIRED = "EXPIRED", _("Expired")
    REJECTED = "REJECTED", _("Rejected")


class InvitationRole(models.TextChoices):
    """
    Defines the roles that can be offered through an invitation.
    Used to specify what position a new employee is being invited to fill.
    """

    MAINTENANCE = "MAINTENANCE", _("Maintenance Agent")
    GUARD = "GUARD", _("Guard")

class PageSize(StrEnum):
    """Supported PDF page sizes."""
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    LETTER = "LETTER"
    LEGAL = "LEGAL"

class Orientation(StrEnum):
    """Supported PDF orientations."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"

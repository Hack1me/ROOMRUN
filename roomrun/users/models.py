# ALL IMPORTS
from typing import ClassVar

from core.models.base import BaseModel
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from users.managers import UserManager
from utils.enums import EmployeeStatus
from utils.enums import GuardShift


class User(BaseModel, AbstractUser):
    """
    Default custom user model for ROOMRUN.
    Inherits from AbstractUser (handles passwords, permissions, etc.) and BaseModel
    (which likely provides id, created_at, updated_at).
    """

    # -------------------------------------------------------------------------
    # Authentication
    # -------------------------------------------------------------------------

    # Disable the native 'username' field from Django.
    username = None

    # Custom manager for user queries.
    objects: ClassVar[UserManager] = UserManager()

    # Use 'email' as the primary login identifier.
    USERNAME_FIELD = "email"
    # Additional fields required when creating a superuser (besides email).
    REQUIRED_FIELDS = []

    # -------------------------------------------------------------------------
    # Choices (Enums)  # noqa: ERA001
    # -------------------------------------------------------------------------

    class UserStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        INACTIVE = "INACTIVE", _("Inactif")
        SUSPENDED = "SUSPENDED", _("Suspendu")

    # -------------------------------------------------------------------------
    # Personal information
    # -------------------------------------------------------------------------

    email = models.EmailField(
        _("email address"),
        unique=True,  # Email must be unique across the entire database.
    )

    phone = PhoneNumberField(
        _("phone number"),
        unique=True,
        null=True,    # Allows NULL in the database (since unique=True + null=True is supported,  # noqa: E501
        blank=True,   # but be careful with duplicate NULLs on some database backends).
    )

    country = CountryField(
        _("country"),
        null=True,
        blank=True,
    )

    profile_picture = models.ImageField(
        _("profile picture"),
        upload_to="users/profile/",  # Storage folder within MEDIA_ROOT.
        null=True,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Account status
    # -------------------------------------------------------------------------

    status = models.CharField(
        _("user status"),
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
        db_index=True,  # Indexed for frequent filtering on this field.
    )

    # -------------------------------------------------------------------------
    # Verification
    # -------------------------------------------------------------------------

    email_verified = models.BooleanField(
        _("email verified"),
        default=False,
    )

    phone_verified = models.BooleanField(
        _("phone verified"),
        default=False,
    )

    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        # NOTE: This field is redundant with the two above.
        # It should likely be a computed property.
    )

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------

    last_login_ip = models.GenericIPAddressField(
        _("last login IP"),
        null=True,
        blank=True,
    )

    # -------------------------------------------------------------------------
    # Meta
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "users"  # Explicit database table name.
        ordering = ["-created_at"]  # Default ordering (newest first).
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [
            models.Index(
                fields=["status"],
                name="user_status_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="user_created_at_idx",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        # Falls back to email if full_name is empty.
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        """Return the concatenated first and last name, stripped of extra spaces."""
        return f"{self.first_name} {self.last_name}".strip()

    def is_active_user(self) -> bool:
        """Check if the account status is ACTIVE."""
        return self.status == self.UserStatus.ACTIVE

    def get_absolute_url(self) -> str:
        """Canonical URL to the user detail page."""
        return reverse(
            "users:detail",
            kwargs={"pk": self.id},
        )


# -------------------------------------------------------------------------
# LANDLORD
# -------------------------------------------------------------------------
class Landlord(BaseModel):
    """
    Business profile representing a landlord in ROOMRUN.
    Linked to a user via a OneToOne relationship.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,  # Best practice: use the customizable AUTH_USER_MODEL setting.
        on_delete=models.CASCADE,
        related_name="landlord_profile",
        verbose_name=_("User"),
    )

    landlord_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,  # Auto-generated (but NO generation logic is currently implemented).
        verbose_name=_("Landlord number"),
        help_text=_(
            "Auto-generated unique identifier for the landlord."
        ),
    )

    verified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Verified"),
        help_text=_(
            "Indicates if the landlord's identity has been verified."
        ),
    )

    class Meta:
        db_table = "landlords"
        ordering = ["-created_at"]
        verbose_name = _("Landlord")
        verbose_name_plural = _("Landlords")

    def __str__(self) -> str:
        # Delegates display to the associated user.
        return str(self.user)

    def get_absolute_url(self) -> str:
        return reverse(
            "users:landlord-detail",
            kwargs={"pk": self.id},
        )


# -------------------------------------------------------------------------
# TENANT
# -------------------------------------------------------------------------
class Tenant(BaseModel):
    """
    Business profile representing a tenant in ROOMRUN.
    Linked to a user.
    """

    user = models.OneToOneField(
        User,  # INCONSISTENCY: Should use settings.AUTH_USER_MODEL.
        on_delete=models.CASCADE,
        related_name="tenant_profile",
    )

    tenant_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,  # No generation logic provided.
    )

    nationality = models.CharField(
        max_length=100,
        blank=True,
    )

    occupation = models.CharField(
        max_length=150,
        blank=True,
    )

    verified = models.BooleanField(
        default=False,
    )

    # INCONSISTENCY: These fields already exist in BaseModel.
    # This will cause a migration conflict or duplicate columns in the database.
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]
        # Missing verbose_name and verbose_name_plural

    def __str__(self) -> str:
        # Directly retrieves full_name or email from the user.
        return self.user.full_name or self.user.email

    def get_absolute_url(self) -> str:
        return reverse(
            "users:tenant-detail",
            kwargs={"pk": self.id},
        )


# -------------------------------------------------------------------------
# EMPLOYEE
# -------------------------------------------------------------------------
class Employee(BaseModel):
    """
    Business profile representing an employee in ROOMRUN.
    Linked to a user.
    """

    user = models.OneToOneField(
        User,  # INCONSISTENCY: Should use settings.AUTH_USER_MODEL.
        on_delete=models.CASCADE,
        related_name="employee_profile",
        verbose_name=_("User"),
    )

    employee_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name=_("Employee number"),
        help_text=_(
            "Auto-generated unique identifier for the employee."
        ),
    )

    job_title = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Job title"),
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
        # NOTE: This duplicates User.status. Risk of desynchronization.
    )

    hire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Hire date"),
    )

    class Meta:
        db_table = "employees"
        ordering = ["-created_at"]
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")

        indexes = [
            models.Index(
                fields=["hire_date"],
                name="employee_hire_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.user.full_name or self.user.email

    def get_absolute_url(self) -> str:
        return reverse(
            "users:employee-detail",
            kwargs={"pk": self.id},
        )


# -------------------------------------------------------------------------
# MAINTENANCE AGENT
# -------------------------------------------------------------------------
class MaintenanceAgent(BaseModel):
    """
    Business profile representing a maintenance agent in ROOMRUN.
    A maintenance agent is a specialized employee.
    """

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="maintenance_agent_profile",
        verbose_name=_("Employee"),
    )

    agent_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name=_("Agent number"),
        help_text=_(
            "Auto-generated unique identifier for the maintenance agent."
        ),
    )

    speciality = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Speciality"),
        help_text=_(
            "Technical speciality of the maintenance agent."
        ),
    )

    class Meta:
        db_table = "maintenance_agents"
        ordering = ["-created_at"]
        verbose_name = _("Maintenance agent")
        verbose_name_plural = _("Maintenance agents")

    def __str__(self) -> str:
        return str(self.employee)

    def get_absolute_url(self) -> str:
        return reverse(
            "employee:maintenance-agent-detail",  # Different namespace ('employee' vs 'users')
            kwargs={"pk": self.id},
        )


# -------------------------------------------------------------------------
# GUARD
# -------------------------------------------------------------------------
class Guard(BaseModel):
    """
    Business profile representing a security guard in ROOMRUN.
    A guard is a specialized employee.
    """

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="guard_profile",
        verbose_name=_("Employee"),
    )

    guard_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name=_("Guard number"),
        help_text=_(
            "Auto-generated unique identifier for the guard."
        ),
    )

    shift = models.CharField(
        max_length=20,
        choices=GuardShift.choices,
        default=GuardShift.DAY,
        verbose_name=_("Shift"),
    )

    class Meta:
        db_table = "guards"
        ordering = ["-created_at"]
        verbose_name = _("Guard")
        verbose_name_plural = _("Guards")

    def __str__(self) -> str:
        return str(self.employee)

    def get_absolute_url(self) -> str:
        return reverse(
            "employee:guard-detail",  # Different namespace ('employee' vs 'users')
            kwargs={"pk": self.id},
        )
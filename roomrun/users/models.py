# =====================================================================
# users/models.py
# =====================================================================
# This module defines all user-related models for the ROOMRUN platform.
# It includes:
#   - User (custom auth model, email as username)
#   - Landlord, Tenant, Employee (business profiles)
#   - MaintenanceAgent, Guard (specialized employees)
#
# All models inherit from BaseModel (provides id, created_at, updated_at).
# All user-facing strings are wrapped in gettext_lazy for internationalization.
# All indexes are centralized in the Meta class for better maintainability.
# =====================================================================

import uuid
from typing import ClassVar

# Core imports
from core.models import BaseModel
from core.validators import validate_phone_number_for_country

# Django & third-party
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField

# Project imports
from users.managers import UserManager
from utils.enums import EmployeeStatus
from utils.enums import GuardShift
from utils.enums import InvitationRole
from utils.enums import InvitationStatus
from utils.enums import OtpPurpose
from utils.enums import UserStatus
from utils.otp import verify_otp_code

MAX_OTP_ATTEMPTS = 5


def default_invitation_expiration():
    """Return the standard seven-day invitation validity period."""
    return timezone.now() + timezone.timedelta(days=7)


# =====================================================================
# USER - Custom authentication model
# =====================================================================


class User(BaseModel, AbstractUser):
    """
    Default custom user model for ROOMRUN.
    - Uses email as the primary login identifier (no username).
    - Inherits from AbstractUser (handles passwords, permissions, groups).
    - Inherits from BaseModel (adds id, created_at, updated_at).
    """

    # -----------------------------------------------------------------
    # Authentication overrides
    # -----------------------------------------------------------------

    # Disable the built-in username field - we use email instead.
    username = None

    # Custom manager (provides create_user, create_superuser, etc.)
    objects: ClassVar[UserManager] = UserManager()

    # Use 'email' as the unique identifier for authentication.
    USERNAME_FIELD = "email"

    # No additional fields required for createsuperuser (email is already required).
    REQUIRED_FIELDS = []

    # -----------------------------------------------------------------
    # Personal information fields
    # -----------------------------------------------------------------

    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text=_("The primary email address used for login and communication."),
    )

    phone = PhoneNumberField(
        _("phone number"),
        unique=True,
        null=True,
        blank=True,
        validators=[validate_phone_number_for_country],
        help_text=_("International format, e.g. +33123456789."),
    )

    country = CountryField(
        _("country"),
        null=True,
        blank=True,
        help_text=_("Country of residence or origin."),
    )

    profile_picture = models.ImageField(
        _("profile picture"),
        upload_to="users/profile/",
        null=True,
        blank=True,
        help_text=_("Upload a profile picture (optional)."),
    )

    # -----------------------------------------------------------------
    # Account status & verification
    # -----------------------------------------------------------------

    status = models.CharField(
        _("user status"),
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
    )

    email_verified = models.BooleanField(
        _("email verified"),
        default=False,
        help_text=_("Indicates if the user has confirmed their email address."),
    )

    phone_verified = models.BooleanField(
        _("phone verified"),
        default=False,
        help_text=_("Indicates if the user has confirmed their phone number."),
    )

    # -----------------------------------------------------------------
    # Security - last login IP
    # -----------------------------------------------------------------

    last_login_ip = models.GenericIPAddressField(
        _("last login IP"),
        null=True,
        blank=True,
        help_text=_("The IP address used during the last successful login."),
    )

    # -----------------------------------------------------------------
    # Meta options with centralized indexes
    # -----------------------------------------------------------------

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        verbose_name = _("user")
        verbose_name_plural = _("users")

        indexes = [
            models.Index(fields=["status"], name="user_status_idx"),
            # Speeds up filtering by account status.
            models.Index(fields=["created_at"], name="user_created_at_idx"),
            # Speeds up ordering by creation date.
        ]

    # -----------------------------------------------------------------
    # Methods
    # -----------------------------------------------------------------

    def __str__(self) -> str:
        """Return full name if available, otherwise email."""
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        """Concatenate first_name and last_name, stripping extra spaces."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_verified(self) -> bool:
        """A user is fully verified if both email and phone are confirmed."""
        return self.email_verified and self.phone_verified

    def is_active_user(self) -> bool:
        """Check if the account status is ACTIVE."""
        return self.status == UserStatus.ACTIVE

    def get_absolute_url(self) -> str:
        """URL to the user detail page (for admin or frontend)."""
        return reverse("users:detail", kwargs={"pk": self.id})


class Otp(BaseModel):
    """A short-lived, single-use code used to verify a sensitive operation."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otps",
        verbose_name=_("user"),
        help_text=_("The user associated with this OTP."),
    )

    purpose = models.CharField(
        _("purpose"),
        max_length=32,
        choices=OtpPurpose.choices,
        help_text=_("The purpose for which this OTP was generated."),
    )

    code_hash = models.CharField(
        _("code hash"),
        max_length=128,
        help_text=_("Hashed representation of the OTP code."),
    )

    expiration_at = models.DateTimeField(
        _("expires at"),
        help_text=_("The date and time after which this OTP is no longer valid."),
    )

    attempts = models.PositiveSmallIntegerField(
        _("attempts"),
        default=0,
        help_text=_("The number of verification attempts made with this OTP."),
    )

    is_used = models.BooleanField(
        _("used"),
        default=False,
        help_text=_("Whether this OTP has been used for verification."),
    )

    class Meta:
        db_table = "user_otps"
        ordering = ["-created_at"]
        verbose_name = _("OTP")
        verbose_name_plural = _("OTPs")

        indexes = [
            models.Index(
                fields=["user", "purpose", "is_used"], name="otp_user_purpose_idx"
            ),
            models.Index(fields=["expiration_at"], name="otp_expiration_idx"),
        ]

    def is_expired(self) -> bool:
        """Return whether this OTP can no longer be used."""
        return timezone.now() >= self.expiration_at

    def can_attempt(self) -> bool:
        """Limit code guesses to reduce brute-force attempts."""
        return self.attempts < MAX_OTP_ATTEMPTS

    def increment_attempts(self) -> None:
        """Record one verification attempt."""
        self.attempts = models.F("attempts") + 1
        self.save(update_fields=["attempts", "updated_at"])
        self.refresh_from_db(fields=["attempts"])

    def is_valid_code(self, code: str) -> bool:
        """Check a submitted code against its password hash."""
        return verify_otp_code(code, self.code_hash)

    def mark_verified(self) -> None:
        """Consume this OTP after a successful verification."""
        self.is_used = True
        self.save(update_fields=["is_used", "updated_at"])


# =====================================================================
# LANDLORD - Business profile for property owners
# =====================================================================


class Landlord(BaseModel):
    """
    Business profile representing a landlord.
    - Linked to a User via OneToOneField.
    - Has a unique, auto-generated landlord_number.
    - May be marked as verified (identity check).
    """

    reference_field = "landlord_number"
    reference_prefix = "LND"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="landlord_profile",
        verbose_name=_("User"),
        help_text=_("The user account associated with this landlord."),
    )

    landlord_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Landlord number"),
        help_text=_("Auto-generated unique identifier for the landlord."),
        # Generated by a pre_save signal in signals.py.
    )

    verified = models.BooleanField(
        default=False,
        verbose_name=_("Verified"),
        help_text=_("Indicates if the landlord's identity has been verified."),
    )

    class Meta:
        db_table = "landlords"
        ordering = ["-created_at"]
        verbose_name = _("Landlord")
        verbose_name_plural = _("Landlords")

        indexes = [
            models.Index(fields=["verified"], name="landlord_verified_idx"),
            # Speeds up filtering by verification status.
        ]

    def __str__(self) -> str:
        """Delegate string representation to the associated user."""
        return str(self.user)

    def get_absolute_url(self) -> str:
        return reverse("users:landlord-detail", kwargs={"pk": self.id})


# =====================================================================
# TENANT - Business profile for renters
# =====================================================================


class Tenant(BaseModel):
    """
    Business profile representing a tenant.
    - Linked to a User via OneToOneField.
    - Has a unique, auto-generated tenant_number.
    - Can store nationality and occupation.
    - May be marked as verified.
    """

    reference_field = "tenant_number"
    reference_prefix = "TEN"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tenant_profile",
        verbose_name=_("User"),
        help_text=_("The user account associated with this tenant."),
    )

    tenant_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Tenant number"),
        help_text=_("Auto-generated unique identifier for the tenant."),
        # Generated by a pre_save signal in signals.py.
    )

    nationality = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Nationality"),
        help_text=_("The tenant's country of nationality."),
    )

    occupation = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Occupation"),
        help_text=_("The tenant's current occupation or profession."),
    )

    verified = models.BooleanField(
        default=False,
        verbose_name=_("Verified"),
        help_text=_("Indicates if the tenant's identity has been verified."),
    )

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]
        verbose_name = _("tenant")
        verbose_name_plural = _("tenants")

        indexes = [
            models.Index(fields=["verified"], name="tenant_verified_idx"),
            # Speeds up filtering by verification status.
        ]

    def __str__(self) -> str:
        return str(self.user)

    def get_absolute_url(self) -> str:
        return reverse("users:tenant-detail", kwargs={"pk": self.id})


# =====================================================================
# EMPLOYEE - Business profile for staff members
# =====================================================================


class Employee(BaseModel):
    """
    Business profile representing an employee.
    - Linked to a User via OneToOneField.
    - Has a unique, auto-generated employee_number.
    - Stores job title, employment status, hire date.
    - Status uses EmployeeStatus enum from utils.enums.
    """

    reference_field = "employee_number"
    reference_prefix = "EMP"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="employee_profile",
        verbose_name=_("User"),
        help_text=_("The user account associated with this employee."),
    )

    employee_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Employee number"),
        help_text=_("Auto-generated unique identifier for the employee."),
        # Generated by a pre_save signal in signals.py.
    )

    job_title = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Job title"),
        help_text=_("The employee's current job title or position."),
    )

    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
        verbose_name=_("Status"),
        help_text=_("Current employment status of the employee."),
    )

    hire_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Hire date"),
        help_text=_("The date the employee was hired."),
    )

    class Meta:
        db_table = "employees"
        ordering = ["-created_at"]
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")

        indexes = [
            models.Index(
                fields=["status"],
                name="employee_status_idx",
            ),
            # Speeds up filtering by employment status.
            models.Index(
                fields=["hire_date"],
                name="employee_hire_date_idx",
            ),
            # Speeds up filtering by hire date.
            models.Index(
                fields=["status", "hire_date"], name="employee_status_hire_idx"
            ),
            # Composite index for combined filtering on status and hire date.
        ]

    def __str__(self) -> str:
        return str(self.user)

    def get_absolute_url(self) -> str:
        return reverse("users:employee-detail", kwargs={"pk": self.id})


# =====================================================================
# MAINTENANCE AGENT - Specialized Employee
# =====================================================================


class MaintenanceAgent(BaseModel):
    """
    Business profile representing a maintenance agent (a specialised employee).
    - Linked to an Employee via OneToOneField.
    - Has a unique, auto-generated agent_number.
    - Stores technical speciality.
    """

    reference_field = "agent_number"
    reference_prefix = "M-AG"

    employee = models.OneToOneField(
        Employee,
        on_delete=models.PROTECT,
        related_name="maintenance_agent_profile",
        verbose_name=_("Employee"),
        help_text=_("The employee record for this maintenance agent."),
    )

    agent_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Agent number"),
        help_text=_("Auto-generated unique identifier for the maintenance agent."),
        # Generated by a pre_save signal in signals.py.
    )

    speciality = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Speciality"),
        help_text=_("Technical speciality of the maintenance agent."),
    )

    class Meta:
        db_table = "maintenance_agents"
        ordering = ["-created_at"]
        verbose_name = _("Maintenance agent")
        verbose_name_plural = _("Maintenance agents")

    def __str__(self) -> str:
        return str(self.employee)

    def get_absolute_url(self) -> str:
        # Using the 'users' namespace for consistency with other profiles.
        return reverse("users:maintenance-agent-detail", kwargs={"pk": self.id})


# =====================================================================
# GUARD - Specialized Employee
# =====================================================================


class Guard(BaseModel):
    """
    Business profile representing a security guard (a specialised employee).
    - Linked to an Employee via OneToOneField.
    - Has a unique, auto-generated guard_number.
    - Stores shift assignment (Day, Night, etc.).
    """

    reference_field = "guard_number"
    reference_prefix = "GRD"

    employee = models.OneToOneField(
        Employee,
        on_delete=models.PROTECT,
        related_name="guard_profile",
        verbose_name=_("Employee"),
        help_text=_("The employee record for this security guard."),
    )

    guard_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Guard number"),
        help_text=_("Auto-generated unique identifier for the guard."),
        # Generated by a pre_save signal in signals.py.
    )

    shift = models.CharField(
        max_length=20,
        choices=GuardShift.choices,
        default=GuardShift.DAY,
        verbose_name=_("Shift"),
        help_text=_("The guard's assigned work shift."),
    )

    class Meta:
        db_table = "guards"
        ordering = ["-created_at"]
        verbose_name = _("Guard")
        verbose_name_plural = _("Guards")

        indexes = [
            models.Index(fields=["shift"], name="guard_shift_idx"),
            # Speeds up filtering by shift assignment.
        ]

    def __str__(self) -> str:
        return str(self.employee)

    def get_absolute_url(self) -> str:
        # Using the 'users' namespace for consistency.
        return reverse("users:guard-detail", kwargs={"pk": self.id})


# =====================================================================
# INVITATION - Gestion des invitations
# =====================================================================


class Invitation(BaseModel):
    """
    Represents an invitation sent by a landlord to a user (new or existing)
    to work as a Maintenance Agent or Guard.
    Supports both:
        - New user: creates a User account with is_active=False
        - Existing user: links to an existing User/Employee
    """

    # -----------------------------------------------------------------
    # Core fields
    # -----------------------------------------------------------------

    email = models.EmailField(
        verbose_name=_("Email"),
        help_text=_("Email address of the invited person."),
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name=_("Token"),
        help_text=_("Unique token for the invitation link."),
    )

    landlord = models.ForeignKey(
        "Landlord",
        on_delete=models.PROTECT,
        related_name="sent_invitations",
        verbose_name=_("Landlord"),
        help_text=_("The landlord who sent the invitation."),
    )

    role = models.CharField(
        max_length=20,
        choices=InvitationRole.choices,
        verbose_name=_("Role"),
        help_text=_("The role being offered: Maintenance Agent or Guard."),
    )

    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the invitation."),
    )

    expires_at = models.DateTimeField(
        default=default_invitation_expiration,
        verbose_name=_("Expires at"),
        help_text=_("The invitation expires after this date."),
    )

    # -----------------------------------------------------------------
    # Link to existing or new User/Employee
    # -----------------------------------------------------------------

    # If the user already exists, link to them
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        verbose_name=_("User"),
        help_text=_("Existing user if they are already registered."),
    )

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
        verbose_name=_("Employee"),
        help_text=_("Existing employee profile if they already have one."),
    )

    # -----------------------------------------------------------------
    # Tracking
    # -----------------------------------------------------------------

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Accepted at"),
        help_text=_("When the invitation was accepted."),
    )

    class Meta:
        db_table = "invitations"
        ordering = ["-created_at"]
        verbose_name = _("Invitation")
        verbose_name_plural = _("Invitations")

        indexes = [
            models.Index(
                fields=["token"],
                name="invitation_token_idx",
            ),
            models.Index(
                fields=["status"],
                name="invitation_status_idx",
            ),
            models.Index(
                fields=["email", "status"],
                name="invitation_email_status_idx",
            ),
            models.Index(
                fields=["expires_at"],
                name="invitation_expires_at_idx",
            ),
        ]

        constraints = [
            # Prevent duplicate pending invitations for the same email,role and landlord
            models.UniqueConstraint(
                fields=["email", "landlord", "role"],
                condition=Q(status="PENDING"),
                name="unique_pending_invitation_per_landlord_role",
            ),
        ]

    def __str__(self) -> str:
        return f"Invitation for {self.email} - {self.role} ({self.status})"

    @property
    def is_expired(self) -> bool:
        """Check if the invitation has expired."""
        return self.expires_at < timezone.now()

    def accept(self, user, employee):
        """
        Mark the invitation as accepted and link it to the user/employee.
        """
        self.status = InvitationStatus.ACCEPTED
        self.user = user
        self.employee = employee
        self.accepted_at = timezone.now()
        self.save()

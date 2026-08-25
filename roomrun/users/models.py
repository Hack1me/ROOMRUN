import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from roomrun.core.models import BaseModel

from .managers import UserManager


# USER
class User(BaseModel,AbstractUser):
    """
    Default custom user model for ROOMRUN.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # UnUsed Fields
    username = None
    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    # Define User Status
    class UserStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        INACTIVE = "INACTIVE", "Inactif"
        SUSPENDED = "SUSPENDED", "Suspendu"

    # Identifier
    id = models.UUIDField(
        _("User Identifier"),
        primary_key=True,
        default=uuid.uuid4,
        editable=True,
    )

    # Email Address
    email = models.EmailField(
        _("email address"),
        unique=True,
    )
    # Phone Number
    phone = models.CharField(
        _("phone number"),
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )

    # User ProfilPicture
    profile_picture = models.ImageField(
        _("User Status"),
        upload_to="users/profile/",
        blank=True,
        null=True,
    )

    # User Status
    status = models.CharField(
        _("User Status"),
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
    )

    # Verifications
    email_verified = models.BooleanField(
        default=False,
    )
    phone_verified = models.BooleanField(
        default=False,
    )

    # Checkers
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    is_verified = models.BooleanField(
        default=False,
    )
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    # Meta
    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="user_status_idx"),
            models.Index(fields=["created_at"], name="user_created_at_idx"),
        ]

    def __str__(self) -> str:
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def is_active_user(self):
        return self.status == self.UserStatus.ACTIVE

    def get_absolute_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.id})


# LANDLORD
class Landlord(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="landlord_profile",
    )

    landlord_number = models.CharField(
        max_length=50,
        unique=True,
    )

    total_properties = models.PositiveIntegerField(
        default=0,
    )

    verified = models.BooleanField(
        default=False,
    )

    nationality = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "landlords"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["verified"],
                name="landlord_verified_idx",
            ),
        ]

    def __str__(self):
        return self.user.full_name or self.user.email


# TENANT
class Tenant(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="tenant_profile",
    )

    tenant_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
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

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.user.full_name or self.user.email

    def get_absolute_url(self) -> str:
        return reverse(
            "users:tenant-detail",
            kwargs={"pk": self.id},
        )

#EMPLOYEE
class Employee(models.Model):
    """
    Business profile representing an employee in ROOMRUN.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )

    employee_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    job_title = models.CharField(
        max_length=150,
        blank=True,
    )

    class EmployeeStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        INACTIVE = "INACTIVE", _("Inactif")
        SUSPENDED = "SUSPENDED", _("Suspendu")

    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
    )

    hire_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "employees"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["status"],
                name="employee_status_idx",
            ),
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

#GUARD
class Guard(models.Model):
    """
    Business profile representing a security guard in ROOMRUN.
    A guard is a specialized employee.
    """

    class GuardShift(models.TextChoices):
        DAY = "DAY", _("Jour")
        NIGHT = "NIGHT", _("Nuit")
        ROTATING = "ROTATING", _("Rotation")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="guard_profile",
    )

    guard_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    shift = models.CharField(
        max_length=20,
        choices=GuardShift.choices,
        default=GuardShift.DAY,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "guards"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.employee.user.full_name or self.employee.user.email

    def get_absolute_url(self) -> str:
        return reverse(
            "users:guard-detail",
            kwargs={"pk": self.id},
        )

#MAINTENANCEAGENT
class MaintenanceAgent(models.Model):
    """
    Business profile representing a maintenance agent in ROOMRUN.
    A maintenance agent is a specialized employee.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="maintenance_agent_profile",
    )

    agent_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
    )

    speciality = models.CharField(
        max_length=150,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "maintenance_agents"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            self.employee.user.full_name
            or self.employee.user.email
        )

    def get_absolute_url(self) -> str:
        return reverse(
            "users:maintenance-agent-detail",
            kwargs={"pk": self.id},
        )

import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


# USER
class User(AbstractUser):
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


import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for ROOMRUN.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # Define Roles
    class Role(models.TextChoices):
            ADMIN = "ADMIN", "Administrateur"
            LANDLORD = "LANDLORD", "Propriétaire"
            TENANT = "TENANT", "Locataire"
            GUARD = "GUARD", "Gardien"
            MAINTENANCE = "MAINTENANCE", "Agent de maintenance"
            GUEST = "GUEST", "Invité"

    # Define User Status
    class UserStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        INACTIVE = "INACTIVE", "Inactif"
        SUSPENDED = "SUSPENDED", "Suspendu"

    # UnUsed Fields
    username = None  # type: ignore[assignment]
    name = None  # type: ignore[assignment]

    # Identifier
    id = models.UUIDField(
        _("User Identifier"),
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        )

    # User Name
    first_name = models.CharField(
        _("User Firstname"),
        max_length=100,
        )
    last_name = models.CharField(
        _("User Lastname"),
        max_length=100,
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

    #User Role
    role = models.CharField(
        _("User Role"),
        max_length=20,
        choices=Role.choices,
        default=Role.GUEST,
    )

    # User Status
    status = models.CharField(
        _("User Status"),
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
    )

    # User ProfilPicture
    profile_picture = models.ImageField(
        _("User Status"),
        upload_to="users/profile/",
        blank=True,
        null=True,
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

    #Meta
    class Meta:
            db_table = "users"
            ordering = ["-created_at"]
            indexes = [
                models.Index(fields=["role"]),
                models.Index(fields=["status"]),
                models.Index(fields=["email"]),
                models.Index(fields=["is_verified"]),
            ]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def __str__(self):
            return self.get_full_name() or self.username

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})

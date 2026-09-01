from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import Employee
from .models import Guard
from .models import Invitation
from .models import Landlord
from .models import MaintenanceAgent
from .models import Tenant
from .models import User


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    """Admin configuration for the email-based user model."""

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "country",
                    "profile_picture",
                )
            },
        ),
        (
            _("Verification"),
            {"fields": ("email_verified", "phone_verified", "status", "last_login_ip")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    list_display = (
        "email",
        "first_name",
        "last_name",
        "status",
        "email_verified",
        "is_staff",
    )
    list_filter = ("status", "email_verified", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)


admin.site.register([Landlord, Tenant, Employee, MaintenanceAgent, Guard, Invitation])

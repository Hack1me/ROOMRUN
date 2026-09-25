from django.contrib import admin

from django.utils.translation import gettext_lazy as _

from .models import CleaningSchedule
from .models import UserInvitation
from .models import VisitorVisit


@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):
    list_display = ("invitation_number", "email", "role", "status", "expires_at")
    list_filter = ("role", "status", "expires_at")
    search_fields = ("invitation_number", "email", "invited_by__email")
    readonly_fields = ("invitation_number", "token_hash", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "invited_by", "role", "status")}),
        (
            _("Invitation details"),
            {
                "fields": (
                    "invitation_number",
                    "token_hash",
                    "expires_at",
                    "accepted_at",
                ),
            },
        ),
        (
            _("Metadata"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


admin.site.register([CleaningSchedule, VisitorVisit])

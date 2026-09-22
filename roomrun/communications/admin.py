from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Announcement
from .models import Conversation
from .models import ConversationParticipant
from .models import Message
from .models import Notification

admin.site.register([Announcement, Notification])


# =============================================================================
# Inlines
# =============================================================================

class ConversationParticipantInline(admin.TabularInline):
    """Manage participants directly from a Conversation."""
    model = ConversationParticipant
    extra = 1
    autocomplete_fields = ["user"]
    readonly_fields = ["last_read_at", "created_at"]


class MessagePreviewInline(admin.TabularInline):
    """Read-only preview of the last messages in the conversation."""
    model = Message
    extra = 0
    fields = ("message_number", "sender", "content", "created_at")
    readonly_fields = ("message_number", "sender", "content", "created_at")
    can_delete = False
    max_num = 5
    ordering = ("-created_at",)

    def has_add_permission(self, request, obj=None):
        return False


# =============================================================================
# Conversation
# =============================================================================

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "conversation_type",
        "participants_count",
        "last_message_at",
        "created_at",
    )
    list_filter = ("conversation_type", "created_at")
    search_fields = (
        "title",
        "participants__email",
        "participants__first_name",
        "participants__last_name",
    )
    readonly_fields = ("last_message_at", "created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = [ConversationParticipantInline, MessagePreviewInline]

    fieldsets = (
        (None, {
            "fields": ("title", "conversation_type")
        }),
        (_("Context"), {
            "fields": ("rental_contract", "maintenance_request"),
            "classes": ("collapse",),
        }),
        (_("Metadata"), {
            "fields": ("last_message_at", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Participants"))
    def participants_count(self, obj):
        return obj.participants.count()


# =============================================================================
# Participant
# =============================================================================

@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "user", "last_read_at", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ["conversation", "user"]
    readonly_fields = ("created_at", "updated_at")


# =============================================================================
# Message
# =============================================================================

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "message_number",
        "conversation",
        "sender",
        "short_content",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "message_number",
        "content",
        "sender__email",
        "conversation__title",
    )
    autocomplete_fields = ["conversation", "sender", "parent_message"]
    readonly_fields = ("message_number", "created_at", "updated_at")
    date_hierarchy = "created_at"

    @admin.display(description=_("Content"))
    def short_content(self, obj):
        preview = (obj.content or "")[:60]
        jls_extract_var = 60
        return f"{preview}…" if len(obj.content or "") > jls_extract_var else preview

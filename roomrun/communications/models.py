from core.models import BaseModel
from core.models import ReadableModelMixin
from core.utils import safe_reverse
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from properties.models import Building
from properties.models import Unit
from users.models import Landlord
from users.models import User
from utils.enums import AnnouncementStatus
from utils.enums import AnnouncementTarget
from utils.enums import ConversationType
from utils.enums import NotificationType


class Announcement(BaseModel):
    """
    Represents an announcement published by a landlord for tenants.
    Announcements can be targeted to specific tenant groups and
    have a defined publication and expiration schedule.
    """

    reference_field = "announcement_number"
    reference_prefix = "ANN"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    announcement_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Announcement number"),
        help_text=_("Auto-generated unique identifier for the announcement."),
        # Generation logic must be added via a signals.py
    )

    landlord = models.ForeignKey(
        Landlord,
        on_delete=models.PROTECT,  # Prevents deletion if announcements exist
        related_name="announcements",
        verbose_name=_("Landlord"),
        help_text=_("The landlord who published this announcement."),
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Title"),
        help_text=_("The headline of the announcement."),
    )

    content = models.TextField(
        verbose_name=_("Content"),
        help_text=_("The full content of the announcement."),
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Published at"),
        help_text=_("The date and time when the announcement was published."),
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expires at"),
        help_text=_("The date and time when the announcement will expire."),
    )

    status = models.CharField(
        max_length=20,
        choices=AnnouncementStatus.choices,
        default=AnnouncementStatus.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current status of the announcement."),
    )

    target = models.CharField(
        max_length=20,
        choices=AnnouncementTarget.choices,
        default=AnnouncementTarget.ALL_TENANTS,
        verbose_name=_("Target"),
        help_text=_("The intended audience for this announcement."),
    )

    building = models.ForeignKey(
        Building,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="announcements",
        verbose_name=_("Building"),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="announcements",
        verbose_name=_("Unit"),
    )

    attachment_url = models.URLField(
        blank=True,
        verbose_name=_("Attachment URL"),
        help_text=_("Optional URL to an external attachment (e.g., PDF, image)."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "announcements"
        ordering = ["-created_at"]
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")

        indexes = [
            models.Index(fields=["landlord"], name="announcement_landlord_idx"),
            models.Index(fields=["status"], name="announcement_status_idx"),
            models.Index(fields=["target"], name="announcement_target_idx"),
            models.Index(fields=["published_at"], name="announcement_published_idx"),
            models.Index(fields=["expires_at"], name="announcement_expires_idx"),
            # Composite index for active announcements filtering
            models.Index(
                fields=["status", "published_at"],
                name="ann_status_published_idx",
            ),
        ]

        # Ensure an announcement number is always unique (enforced at field level)
        # No additional constraints needed for this model.

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the announcement title as string representation."""
        return self.title

    def get_absolute_url(self) -> str:
        """Return the canonical URL for the announcement detail view."""
        return safe_reverse(
            "communications:announcement-detail", kwargs={"pk": self.id}
        )

    @property
    def is_active(self) -> bool:
        """
        Check if the announcement is currently active.
        An announcement is active if:
        - Status is PUBLISHED
        - published_at is set and is in the past
        - expires_at is either null or in the future
        """
        now = timezone.now()
        return (
            self.status == AnnouncementStatus.PUBLISHED
            and self.published_at
            and self.published_at <= now
            and (not self.expires_at or self.expires_at > now)
        )

    @property
    def is_expired(self) -> bool:
        """Check if the announcement has expired."""
        return self.expires_at and self.expires_at <= timezone.now()

    def clean(self):
        super().clean()
        self._clean_target()

        if (
            self.published_at
            and self.expires_at
            and self.expires_at <= self.published_at
        ):
            raise ValidationError(_("Expires at must be after published at."))

        if self.status == AnnouncementStatus.PUBLISHED:
            if not self.published_at:
                raise ValidationError(
                    _("Published at is required when status is PUBLISHED.")
                )
            if self.published_at > timezone.now():
                raise ValidationError(_("Published at cannot be in the future."))

        if self.status == AnnouncementStatus.DRAFT and self.published_at:
            raise ValidationError(
                _("Published at should not be set when status is DRAFT.")
            )

    def _clean_target(self) -> None:
        """Validate that the selected audience has the needed relation."""
        if self.target == AnnouncementTarget.ALL_TENANTS and (
            self.building_id or self.unit_id
        ):
            raise ValidationError(
                _("A general announcement cannot target a building or unit.")
            )
        if self.target == AnnouncementTarget.BUILDING and not self.building_id:
            raise ValidationError(_("A building is required for this target."))
        if self.target == AnnouncementTarget.UNIT and not self.unit_id:
            raise ValidationError(_("A unit is required for this target."))
        if (
            self.unit_id
            and self.building_id
            and self.unit.building_id != self.building_id
        ):
            raise ValidationError(_("The unit must belong to the selected building."))

    def publish(self):
        """
        Helper method to publish the announcement.
        Sets published_at to now and status to PUBLISHED.
        """
        if self.status != AnnouncementStatus.PUBLISHED:
            self.status = AnnouncementStatus.PUBLISHED
            self.published_at = timezone.now()
            self.save()

    def archive(self):
        """
        Helper method to archive the announcement.
        Sets status to ARCHIVED.
        """
        if self.status != AnnouncementStatus.ARCHIVED:
            self.status = AnnouncementStatus.ARCHIVED
            self.save()


class Notification(ReadableModelMixin, BaseModel):
    """
    Represents a notification sent to a user.
    Notifications can be marked as read, and the read timestamp is tracked.
    """

    reference_field = "notification_number"
    reference_prefix = "NTF"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    notification_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Notification number"),
        help_text=_("Auto-generated unique identifier for the notification."),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="notifications",
        verbose_name=_("Recipient"),
        help_text=_("The user who receives this notification."),
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("Title"),
        help_text=_("Short headline of the notification."),
    )

    message = models.TextField(
        verbose_name=_("Message"),
        help_text=_("The full content of the notification."),
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        verbose_name=_("Notification type"),
        help_text=_("The category of this notification."),
    )

    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_contexts",
    )
    related_object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

        indexes = [
            models.Index(fields=["recipient"], name="notification_recipient_idx"),
            models.Index(fields=["is_read"], name="notification_read_idx"),
            models.Index(fields=["notification_type"], name="notification_type_idx"),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return safe_reverse(
            "communications:notification-detail", kwargs={"pk": self.id}
        )


class Conversation(BaseModel):
    """
    A chat thread between two or more users.

    Optional FK links to business objects (contract, maintenance request)
    give the UI a rich header and allow access control.
    """

    conversation_type = models.CharField(
        max_length=30,
        choices=ConversationType.choices,
        db_index=True,
        verbose_name=_("Type"),
    )

    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Title"),
    )

    direct_key = models.CharField(
        max_length=73,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name=_("Direct conversation key"),
        help_text=_("Unique key for a two-person conversation."),
    )

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ConversationParticipant",
        through_fields=("conversation", "user"),
        related_name="conversations",
        verbose_name=_("Participants"),
    )

    # --- Context FKs (all optional) ---

    rental_contract = models.ForeignKey(
        "rentals.RentalContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
        verbose_name=_("Rental contract"),
    )

    maintenance_request = models.ForeignKey(
        "maintenance.MaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
        verbose_name=_("Maintenance request"),
    )

    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last message at"),
    )

    class Meta:
        db_table = "communications_conversations"
        ordering = ["-last_message_at", "-created_at"]
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")

        indexes = [
            models.Index(fields=["last_message_at"], name="conv_last_msg_idx"),
        ]

    def __str__(self) -> str:
        return self.title or f"Conversation #{self.pk}"


class ConversationParticipant(BaseModel):
    """
    Through model for Conversation ↔ User.

    Stores per-user state: when they last read messages in the conversation.
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participant_links",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_links",
    )

    last_read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Timestamp of the last message read by this user."),
    )

    class Meta:
        db_table = "communications_participants"
        verbose_name = _("Conversation participant")
        verbose_name_plural = _("Conversation participants")

        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_participant",
            ),
        ]

        indexes = [
            models.Index(
                fields=["user", "conversation"],
                name="participant_user_conv_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} in conversation #{self.conversation_id}"


class Message(BaseModel):
    """
    A single message posted inside a Conversation.

    Note: read state is tracked per-user at the conversation level
    (see ConversationParticipant.last_read_at).
    """

    reference_field = "message_number"
    reference_prefix = "MSG"

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    message_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        blank=True,
        verbose_name=_("Message number"),
    )

    conversation = models.ForeignKey(
        "communications.Conversation",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Conversation"),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_messages",
        verbose_name=_("Sender"),
    )

    content = models.TextField(
        verbose_name=_("Content"),
    )

    parent_message = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name=_("Reply to"),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "communications_messages"
        ordering = ["created_at"]
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")

        indexes = [
            models.Index(
                fields=["conversation", "-created_at"],
                name="msg_conv_created_idx",
            ),
            models.Index(fields=["sender"], name="msg_sender_idx"),
        ]

    def __str__(self) -> str:
        preview = (self.content or "")[:40]
        return f"[conv #{self.conversation_id}] {self.sender}: {preview}"

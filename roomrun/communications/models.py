from core.models import BaseModel
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from users.models import Landlord
from users.models import User
from utils.enums import AnnouncementStatus
from utils.enums import AnnouncementTarget
from utils.enums import NotificationType


class Announcement(BaseModel):
    """
    Represents an announcement published by a landlord for tenants.
    Announcements can be targeted to specific tenant groups and
    have a defined publication and expiration schedule.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    announcement_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
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
                name="announcement_status_published_idx",
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
        return reverse("communications:announcement-detail", kwargs={"pk": self.id})

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
        """
        Business-rule validations:
        1. published_at must be before expires_at (if both provided).
        2. published_at is required when status is PUBLISHED.
        3. published_at should be null when status is DRAFT.
        4. expires_at must be after published_at (if published_at is set).
        """
        # Validate date order
        if self.published_at and self.expires_at:
            if self.expires_at <= self.published_at:
                raise ValidationError(_("Expires at must be after published at."))

        # Status validation
        if self.status == AnnouncementStatus.PUBLISHED:
            if not self.published_at:
                raise ValidationError(
                    _("Published at is required when status is PUBLISHED.")
                )
            if self.published_at > timezone.now():
                raise ValidationError(_("Published at cannot be in the future."))

        # DRAFT announcements should not have published_at
        if self.status == AnnouncementStatus.DRAFT and self.published_at:
            raise ValidationError(
                _("Published at should not be set when status is DRAFT.")
            )

        # Expired validation (if expires_at is set, it must be in the future)
        if self.expires_at and self.expires_at <= timezone.now():
            # Allow setting expired announcements only if status is not DRAFT
            pass  # This can be allowed; it's a valid state.

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

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


class Notification(BaseModel):
    """
    Represents a notification sent to a user.
    Notifications can be marked as read, and the read timestamp is tracked.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    notification_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Notification number"),
        help_text=_("Auto-generated unique identifier for the notification."),
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
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

    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Read"),
        help_text=_("Indicates whether the notification has been read."),
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Read at"),
        help_text=_("The timestamp when the notification was read."),
    )

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
        return reverse("communications:notification-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. If is_read is True, read_at must be set.
        2. If is_read is False, read_at must be null.
        3. read_at cannot be in the future.
        """
        if self.is_read and not self.read_at:
            raise ValidationError(
                _("Read at must be set when the notification is marked as read.")
            )
        if not self.is_read and self.read_at:
            raise ValidationError(
                _("Read at should be empty when the notification is not read.")
            )
        if self.read_at and self.read_at > timezone.now():
            raise ValidationError(_("Read at cannot be in the future."))

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_as_read(self):
        """Mark the notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    def mark_as_unread(self):
        """Mark the notification as unread."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()

    @property
    def is_unread(self) -> bool:
        return not self.is_read


class Message(BaseModel):
    """
    Represents a direct message between two users in ROOMRUN.
    Messages track their read status and support threading if needed.
    """

    # -------------------------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------------------------

    message_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name=_("Message number"),
        help_text=_("Auto-generated unique identifier for the message."),
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name=_("Sender"),
        help_text=_("The user who sent the message."),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
        verbose_name=_("Recipient"),
        help_text=_("The user who received the message."),
    )

    content = models.TextField(
        verbose_name=_("Content"),
        help_text=_("The actual content of the message."),
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Read"),
        help_text=_("Indicates whether the message has been read by the recipient."),
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Read at"),
        help_text=_("The timestamp when the message was read."),
    )

    # -------------------------------------------------------------------------
    # Meta Options
    # -------------------------------------------------------------------------

    class Meta:
        db_table = "messages"
        ordering = ["-created_at"]
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")

        indexes = [
            models.Index(fields=["sender"], name="message_sender_idx"),
            models.Index(fields=["recipient"], name="message_recipient_idx"),
            models.Index(fields=["is_read"], name="message_read_idx"),
            models.Index(fields=["created_at"], name="message_created_at_idx"),
            # Composite index for filtering unread messages for a specific recipient
            models.Index(
                fields=["recipient", "is_read"],
                name="message_recipient_read_idx",
            ),
        ]

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """Return a human-readable representation of the message."""
        return f"{self.sender} → {self.recipient}"

    def get_absolute_url(self) -> str:
        return reverse("communications:message-detail", kwargs={"pk": self.id})

    def clean(self):
        """
        Business-rule validations:
        1. Prevent users from sending messages to themselves.
        2. If is_read is True, read_at must be set.
        3. If is_read is False, read_at must be null.
        4. read_at cannot be in the future.
        """
        # Prevent self-messaging
        if self.sender and self.recipient and self.sender == self.recipient:
            raise ValidationError(_("You cannot send a message to yourself."))

        # Read status validation
        if self.is_read and not self.read_at:
            raise ValidationError(
                _("Read at must be set when the message is marked as read.")
            )
        if not self.is_read and self.read_at:
            raise ValidationError(
                _("Read at should be empty when the message is not read.")
            )
        if self.read_at and self.read_at > timezone.now():
            raise ValidationError(_("Read at cannot be in the future."))

    def save(self, *args, **kwargs):
        """Run full validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)

    def mark_as_read(self):
        """Mark the message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()

    def mark_as_unread(self):
        """Mark the message as unread."""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()

    @property
    def is_unread(self) -> bool:
        return not self.is_read

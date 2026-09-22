# communications/services/conversation.py

from communications.models import Conversation
from communications.models import ConversationParticipant
from communications.models import ConversationType
from communications.models import Message
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ConversationService:
    """
    Business logic for conversations and messages.

    All methods assume the calling code has already checked permissions.
    """

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_conversation(  # noqa: PLR0913
        *,
        participants,
        conversation_type: str,
        title: str = "",
        rental_contract=None,
        maintenance_request=None,
        direct_key: str | None = None,
    ) -> Conversation:
        """
        Create a new conversation with the given participants.

        Args:
            participants: An iterable of User instances (at least 2).
            conversation_type: One of ConversationType.choices.
            title: Optional display title.
            rental_contract: Optional RentalContract instance.
            maintenance_request: Optional MaintenanceRequest instance.

        Returns:
            The created Conversation.

        Raises:
            ValidationError: If fewer than 2 participants are provided
                or the conversation_type is invalid.
        """
        participants = list(participants)

        if len(participants) < 2:  # noqa: PLR2004
            raise ValidationError(
                _("A conversation must have at least two participants.")
            )

        if conversation_type not in ConversationType.values:
            raise ValidationError(_("Invalid conversation type."))

        conversation = Conversation.objects.create(
            conversation_type=conversation_type,
            title=title,
            rental_contract=rental_contract,
            maintenance_request=maintenance_request,
            direct_key=direct_key,
        )

        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(conversation=conversation, user=user)
            for user in participants
        ])

        return conversation

    @staticmethod
    def get_or_create_direct_conversation(
        *, user, recipient
    ) -> tuple[Conversation, bool]:
        """Return the single direct thread for two users, creating it safely."""
        direct_key = ":".join(sorted((str(user.pk), str(recipient.pk))))
        conversation = Conversation.objects.filter(direct_key=direct_key).first()
        if conversation:
            return conversation, False

        # Reuse a direct conversation created before ``direct_key`` existed.
        conversation = (
            Conversation.objects.filter(participants=user)
            .filter(participants=recipient)
            .annotate(participant_count=Count("participants", distinct=True))
            .filter(participant_count=2)
            .order_by("-last_message_at", "-created_at")
            .first()
        )
        if conversation:
            try:
                conversation.direct_key = direct_key
                conversation.save(update_fields=["direct_key", "updated_at"])
            except IntegrityError:
                conversation = Conversation.objects.get(direct_key=direct_key)
            return conversation, False

        conversation_type = (
            ConversationType.LANDLORD_TENANT
            if hasattr(recipient, "tenant_profile")
            else ConversationType.LANDLORD_STAFF
            if hasattr(recipient, "employee_profile")
            else ConversationType.SUPPORT
        )
        try:
            with transaction.atomic():
                conversation = ConversationService.create_conversation(
                    participants=[user, recipient],
                    conversation_type=conversation_type,
                    title=recipient.full_name or recipient.email,
                    direct_key=direct_key,
                )
        except IntegrityError:
            conversation = Conversation.objects.get(direct_key=direct_key)
            return conversation, False

        return conversation, True

    # -------------------------------------------------------------------------
    # Retrieve
    # -------------------------------------------------------------------------

    @staticmethod
    def get_for_user(*, user, conversation_id: int) -> Conversation:
        """
        Return a conversation the given user is a participant of.

        Raises:
            ValidationError: If the user is not a participant.
        """
        try:
            return (
                Conversation.objects
                .prefetch_related("participants")
                .get(pk=conversation_id, participants=user)
            )
        except Conversation.DoesNotExist:
            raise ValidationError(  # noqa: B904
                _("Conversation not found or you are not a participant.")
            )

    # -------------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def post_message(
        *,
        conversation: Conversation,
        sender,
        content: str,
        parent_message: Message | None = None,
    ) -> Message:
        """
        Post a message in the given conversation.

        Validates:
        - content is not empty
        - sender is a participant of the conversation

        The `last_message_at` denormalized field is updated via a
        post_save signal (see communications/signals.py).
        """
        content = (content or "").strip()

        if not content:
            raise ValidationError(_("Message content cannot be empty."))

        # Ensure the sender is a participant.
        is_participant = ConversationParticipant.objects.filter(
            conversation=conversation,
            user=sender,
        ).exists()

        if not is_participant:
            raise ValidationError(
                _("The sender is not a participant of this conversation.")
            )

        # Validate parent_message belongs to the same conversation.
        if parent_message and parent_message.conversation_id != conversation.id:
            raise ValidationError(
                _("The parent message belongs to another conversation.")
            )

        return Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            parent_message=parent_message,
        )

    # -------------------------------------------------------------------------
    # Read state
    # -------------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def mark_as_read(*, conversation: Conversation, user) -> None:
        """
        Mark all messages in the conversation as read for the given user.
        """
        ConversationParticipant.objects.filter(
            conversation=conversation,
            user=user,
        ).update(last_read_at=timezone.now())

    @staticmethod
    def unread_count(*, conversation: Conversation, user) -> int:
        """
        Return the number of unread messages for the given user
        in the given conversation.

        A message is unread if it was created after the user's
        `last_read_at`, and it was not sent by the user.
        """
        link = ConversationParticipant.objects.filter(
            conversation=conversation,
            user=user,
        ).first()

        if not link or not link.last_read_at:
            return (
                conversation.messages
                .exclude(sender=user)
                .count()
            )

        return (
            conversation.messages
            .filter(created_at__gt=link.last_read_at)
            .exclude(sender=user)
            .count()
        )

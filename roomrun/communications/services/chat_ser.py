# communications/services/conversation.py

from communications.models import Conversation
from communications.models import ConversationParticipant
from communications.models import ConversationType
from communications.models import Message
from django.core.exceptions import ValidationError
from django.db import transaction
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
    def create_conversation(
        *,
        participants,
        conversation_type: str,
        title: str = "",
        rental_contract=None,
        maintenance_request=None,
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
        )

        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(conversation=conversation, user=user)
            for user in participants
        ])

        return conversation

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

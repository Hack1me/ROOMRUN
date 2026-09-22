import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from communications.models import Conversation
from communications.models import ConversationParticipant
from communications.services.chat_ser import ConversationService
from django.core.exceptions import ValidationError


class ConversationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single conversation.

    URL: ws/communications/conversation/<conversation_id>/

    Incoming events (JSON):
        {"type": "message", "content": "Hello"}
        {"type": "typing", "is_typing": true}
        {"type": "read"}

    Outgoing events (JSON):
        {"type": "message", "id": ..., "sender": {...}, "content": ..., ...}
        {"type": "typing", "user_id": ..., "is_typing": ...}
        {"type": "read", "user_id": ..., "at": ...}
        {"type": "error", "detail": "..."}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_id = None
        self.group_name = None
        self.user = None

    # -------------------------------------------------------------------------
    # Connection lifecycle
    # -------------------------------------------------------------------------

    async def connect(self):
        self.user = self.scope["user"]

        # Reject anonymous connections.
        if not self.user or self.user.is_anonymous:
            await self.close(code=4401)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"

        # Reject non-participants.
        is_participant = await self._is_participant(
            self.conversation_id, self.user.id
        )
        if not is_participant:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Mark as read on connect.
        await self._mark_as_read(self.conversation_id, self.user)

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    # -------------------------------------------------------------------------
    # Incoming events
    # -------------------------------------------------------------------------

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON.")
            return

        event_type = payload.get("type")

        if event_type == "message":
            await self._handle_message(payload)
        elif event_type == "typing":
            await self._handle_typing(payload)
        elif event_type == "read":
            await self._handle_read()
        else:
            await self._send_error(f"Unknown event type: {event_type}")

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    async def _handle_message(self, payload):
        content = (payload.get("content") or "").strip()
        if not content:
            await self._send_error("Message content is required.")
            return

        try:
            message_data = await self._create_message(
                self.conversation_id, self.user, content
            )
        except ValidationError as error:
            await self._send_error(error.messages[0])
            return

        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "message": message_data},
        )

    async def _handle_typing(self, payload):
        is_typing = bool(payload.get("is_typing", False))
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.typing",
                "user_id": str(self.user.id),
                "is_typing": is_typing,
            },
        )

    async def _handle_read(self):
        await self._mark_as_read(self.conversation_id, self.user)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.read",
                "user_id": str(self.user.id),
            },
        )

    # -------------------------------------------------------------------------
    # Group event handlers (called by the channel layer)
    # -------------------------------------------------------------------------

    async def chat_message(self, event):
        """Broadcast a new message to all connected clients."""
        await self.send(text_data=json.dumps({
            "type": "message",
            **event["message"],
        }))

    async def chat_typing(self, event):
        """Broadcast a typing indicator (skip echoing back to sender)."""
        if event["user_id"] == str(self.user.id):
            return
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user_id": event["user_id"],
            "is_typing": event["is_typing"],
        }))

    async def chat_read(self, event):
        """Broadcast a read receipt."""
        await self.send(text_data=json.dumps({
            "type": "read",
            "user_id": event["user_id"],
        }))

    # -------------------------------------------------------------------------
    # DB helpers (must be sync, wrapped with database_sync_to_async)
    # -------------------------------------------------------------------------

    @database_sync_to_async
    def _is_participant(self, conversation_id, user_id) -> bool:
        return ConversationParticipant.objects.filter(
            conversation_id=conversation_id,
            user_id=user_id,
        ).exists()

    @database_sync_to_async
    def _create_message(self, conversation_id, user, content) -> dict:
        conversation = Conversation.objects.get(pk=conversation_id)
        message = ConversationService.post_message(
            conversation=conversation,
            sender=user,
            content=content,
        )

        return {
            "id": str(message.id),
            "message_number": message.message_number,
            "sender": {
                "id": str(user.id),
                "full_name": user.full_name,
            },
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }

    @database_sync_to_async
    def _mark_as_read(self, conversation_id, user):
        conversation = Conversation.objects.get(pk=conversation_id)
        ConversationService.mark_as_read(conversation=conversation, user=user)

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    async def _send_error(self, detail):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))

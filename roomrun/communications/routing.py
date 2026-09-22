from communications.consumers import ConversationConsumer
from django.urls import re_path

websocket_urlpatterns = [
    re_path(
        r"^ws/communications/conversation/"
        r"(?P<conversation_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$",
        ConversationConsumer.as_asgi(),
    ),
]

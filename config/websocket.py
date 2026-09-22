from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from communications.routing import websocket_urlpatterns

websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    )
)

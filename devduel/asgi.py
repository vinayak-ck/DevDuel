# devduel/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'devduel.settings')

# initialize Django before importing anything that uses models
django_asgi_app = get_asgi_application()

# import routing AFTER django setup
import battle.routing

application = ProtocolTypeRouter({
    # HTTP → regular Django views (nothing changes here)
    'http': django_asgi_app,

    # WebSocket → goes through auth, then your URL router
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                battle.routing.websocket_urlpatterns
            )
        )
    ),
})
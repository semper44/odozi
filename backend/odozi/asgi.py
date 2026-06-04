"""
ASGI config for odozi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator


from odozi.middleware import CookieJwtAuthMiddleware
from . import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'odozi.settings')

django_asgi_app = get_asgi_application()


application = ProtocolTypeRouter({
    # Explicitly map standard HTTP requests using Django's native application
    "http": django_asgi_app,
    
    # Map WebSocket connections through your auth stack and router
    "websocket": AllowedHostsOriginValidator(
        CookieJwtAuthMiddleware(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    ),
})

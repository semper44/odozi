from django.urls import path
from . import consumers

websocket_urlpatterns = [
    # Use path() for exact matches (Recommended)
    path("ws/chat/", consumers.ChatConsumer.as_asgi()),
   
]

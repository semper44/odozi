from django.urls import path
from . import consumers

websocket_urlpatterns = [
    # Use path() for exact matches (Recommended)
    path("ws/chat/<str:room_name>/", consumers.ChatConsumer.as_asgi()),
    
    # Or use re_path() only if you require regular expressions
    # re_path(r"ws/chat/(?P<room_name>\w+)/$", consumers.ChatConsumer.as_asgi()),
]

from django.urls import path

from .views import get_websocket_ticket, github_callback_view, github_push_webhook


urlpatterns = [
    # Matches: http://127.0.0
    path("api/auth/github/callback/", github_callback_view, name="github_callback"),
    path("github_push/", github_push_webhook, name="github_push"),
    path("api/auth/ws-ticket/", get_websocket_ticket, name="ws_ticket"),
]

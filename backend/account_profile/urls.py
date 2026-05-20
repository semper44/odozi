from django.urls import path

from .views import github_callback_view, github_installation_webhook


urlpatterns = [
    # Matches: http://127.0.0
    path("api/auth/github/callback/", github_callback_view, name="github_callback"),
    path("api/auth/github/installation/", github_installation_webhook, name="github_installation"),
]

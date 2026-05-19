from django.urls import path

from .views import github_callback_view


urlpatterns = [
    # Matches: http://127.0.0
    path("api/auth/github/callback/", github_callback_view, name="github_callback"),
]

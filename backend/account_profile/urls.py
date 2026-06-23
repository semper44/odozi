from django.urls import path

from .views import  (github_callback_view, github_push_webhook, GitHubRefreshView, 
                     github_ticket, SaveLLMConfigView)


urlpatterns = [
    # Matches: http://127.0.0
    path("api/auth/github/callback/", github_callback_view, name="github_callback"),
    path("github_push/", github_push_webhook, name="github_push"),
    path("api/auth/ws-ticket/", github_ticket, name="github_ticket"),
    path("api/auth/token/refresh/", GitHubRefreshView.as_view(), name="github_refresh"),
    path('api/ai/config/save/', SaveLLMConfigView.as_view(), name='save_llm_config'),

]

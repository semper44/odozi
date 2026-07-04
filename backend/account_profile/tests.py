import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory

from account_profile.models import UserLLMConfig
from account_profile.views import SaveLLMConfigView, github_push_webhook, github_ticket


class AccountProfileViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.api_factory = APIRequestFactory()

    def test_save_llm_config_view_persists_encrypted_settings(self):
        user = User.objects.create_user(username="tester", password="secret")
        request = self.api_factory.post(
            "/account_profile/save-llm-config/",
            {"provider": "openai", "model_name": "gpt-4.1", "api_key": "secret-key"},
            format="json",
        )

        with patch("account_profile.views.User.objects.get", return_value=user):
            response = SaveLLMConfigView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        config = UserLLMConfig.objects.get(user=user)
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model_name, "gpt-4.1")
        self.assertTrue(config.get_api_key())

    def test_github_ticket_returns_ticket_for_valid_cookie(self):
        ticket_id = "ticket-123"
        cache.set(f"redis_auth_ws_transit_ticket:{ticket_id}", {"status": "ready"})
        request = self.factory.post(
            "/account/api/auth/github/ticket/",
            HTTP_COOKIE=f"ticket_id={ticket_id}",
        )

        response = github_ticket(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["ticket"], ticket_id)

    def test_github_push_webhook_rejects_invalid_signature(self):
        payload = b'{"ref": "refs/heads/main"}'
        request = self.factory.post(
            "/account/api/github/webhook/",
            data=payload,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
        )

        with patch("account_profile.views.settings.GITHUB_APP_CLIENT_SECRET", "shared-secret"):
            response = github_push_webhook(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid signature", json.loads(response.content)["error"])

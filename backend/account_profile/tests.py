import json
import urllib.parse
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIRequestFactory

from account_profile.models import UserLLMConfig, Workspace, WorkspaceMembership
from account_profile.views import (
    SaveLLMConfigView,
    github_push_webhook,
    github_login_view,
    github_callback_view,
)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
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

    def test_github_login_view_creates_session_and_signed_state(self):
        request = self.factory.get("/account/api/auth/login/")
        # Attach session to request
        session_middleware = MagicMock()
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        response = github_login_view(request)

        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertIn("https://github.com/login/oauth/authorize", redirect_url)
        self.assertIn("redirect_uri=", redirect_url)
        self.assertIn("state=", redirect_url)

        # Check session
        stored_state = request.session.get("github_oauth_state")
        self.assertTrue(stored_state)

        # Verify state is signed and loadable
        payload = signing.loads(stored_state, salt="github_oauth_state")
        self.assertIn("nonce", payload)
        self.assertIn("frontend", payload)

    def test_github_callback_view_rejects_missing_code(self):
        request = self.factory.get("/account/api/auth/github/callback/")
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        response = github_callback_view(request)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "No authorization code returned from GitHub")

    def test_github_callback_view_rejects_missing_or_invalid_state(self):
        request = self.factory.get("/account/api/auth/github/callback/?code=123&state=tampered")
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        response = github_callback_view(request)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["error"], "Missing or invalid OAuth state")

    def test_github_callback_view_accepts_signed_state_even_if_session_lost(self):
        state = signing.dumps({"nonce": "abc123", "ts": 12345}, salt="github_oauth_state")
        request = self.factory.get(f"/account/api/auth/github/callback/?code=dummycode&state={state}")
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()  # Empty session (simulating lost cookie)

        with patch("account_profile.views.requests.post") as mock_post:
            mock_post.return_value.status_code = 400
            mock_post.return_value.json.return_value = {"error": "bad_code"}

            response = github_callback_view(request)

            # It passed the state check and proceeded to token exchange!
            self.assertNotEqual(response.status_code, 400 if "Missing" in str(response.content) else 999)
            data = json.loads(response.content)
            self.assertNotIn("Missing or invalid OAuth state", data.get("error", ""))

    @patch("account_profile.views.requests.post")
    @patch("account_profile.views.requests.get")
    @patch("account_profile.views.cache")
    @patch("account_profile.views.get_browser_family", return_value="test-browser")
    def test_github_callback_uses_github_user_for_workspace_owner(
        self, _mock_browser_family, _mock_cache, mock_get, mock_post
    ):
        state = signing.dumps(
            {"nonce": "abc123", "ts": 12345, "frontend": "http://localhost:5173"},
            salt="github_oauth_state",
        )
        request = self.factory.get(
            "/account/api/auth/github/callback/",
            {"code": "dummycode", "state": state},
        )
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.backends.db import SessionStore

        request.user = AnonymousUser()
        request.session = SessionStore()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "github-access-token",
            "refresh_token": "github-refresh-token",
            "expires_in": 3600,
        }
        mock_get.return_value.json.return_value = {
            "login": "github-test-user",
            "email": "github-test@example.com",
        }

        response = github_callback_view(request)

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="github-test-user")
        workspace = Workspace.objects.get(name="github-test-user")
        self.assertEqual(workspace.owner, user)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=workspace,
                members=user,
                role="admin",
            ).exists()
        )

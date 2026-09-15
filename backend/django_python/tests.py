import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from account_profile.models import GitHubRepository, Workspace
from django_python.models import RepoEnvKey
from django_python.views import CreateRepoEnvKeys, CreateUsersRepo, CreateWorkspaceView, receive_ci_results


class DjangoPythonViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.api_factory = APIRequestFactory()

    def test_create_workspace_view_returns_created_response(self):
        user = User.objects.create_user(username="workspace-owner", password="secret")
        request = self.api_factory.post(
            "/django_python/workspaces/",
            {
                "new_workspace_name": "My Workspace",
                "repositories": [
                    {
                        "repo_id": 101,
                        "repo_name": "odozi",
                        "repo_owner": "semper44",
                        "repo_full_name": "semper44/odozi",
                    }
                ],
            },
            format="json",
        )
        force_authenticate(request, user=user)

        with patch("django_python.views.create_workspace_with_repos", return_value={
            "total_processed": 1,
            "workspace_id": 42,
            "workspace_name": "My Workspace",
            "saved_count": 1,
        }) as mocked_service:
            response = CreateWorkspaceView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        mocked_service.assert_called_once()
        self.assertEqual(response.data["workspace_name"], "My Workspace")

    def test_create_repo_env_keys_creates_repo_and_environment_keys(self):
        user = User.objects.create_user(username="env-owner", password="secret")
        Workspace.objects.create(name="default", owner=user, github_account_name=user.username)
        request = self.api_factory.post(
            "/django_python/repo-env-keys/",
            {
                "workspace": "default",
                "key_names": ["API_KEY"],
                "selected": [999],
                "repositories": [
                    {
                        "repo_id": 999,
                        "repo_name": "repo-a",
                        "repo_owner": "octocat",
                        "repo_full_name": "octocat/repo-a",
                    }
                ],
            },
            format="json",
        )

        response = CreateRepoEnvKeys.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(GitHubRepository.objects.filter(repo_id=999).exists())
        self.assertTrue(RepoEnvKey.objects.filter(key_name="API_KEY").exists())

    def test_create_users_repo_creates_repository_records(self):
        user = User.objects.create_user(username="repo-owner", password="secret")
        Workspace.objects.create(name="default", owner=user, github_account_name=user.username)
        request = self.api_factory.post(
            "/django_python/user-repos/",
            {
                "workspace": "default",
                "selected": [1234],
                "repositories": [
                    {
                        "repo_id": 1234,
                        "repo_name": "repo-b",
                        "repo_owner": "octocat",
                        "repo_full_name": "octocat/repo-b",
                    }
                ],
            },
            format="json",
        )

        response = CreateUsersRepo.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(GitHubRepository.objects.filter(repo_id=1234).exists())

    def test_receive_ci_results_queues_payload(self):
        user = User.objects.create_user(username="octocat", password="secret")
        request = self.factory.post(
            "/django_python/ci-results/",
            data=json.dumps(
                {
                    "run_id": "run-1",
                    "repo_owner": user.username,
                    "repo": "octocat/test-repo",
                    "tool": "pytest",
                    "logs": ["test passed"],
                }
            ),
            content_type="application/json",
        )

        mock_channel = Mock()
        with patch("django_python.views.get_channel_layer", return_value=mock_channel), patch(
            "django_python.views.process_scan_payload_task.delay"
        ) as mocked_delay:
            response = receive_ci_results(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["status"], "queued")
        mocked_delay.assert_not_called()
        mock_channel.group_send.assert_called_once()

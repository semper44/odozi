import json
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from odozi.views import OptimizedResultsReceiverView


class OdoziViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_django_cache_uses_redis_backend(self):
        self.assertIn("RedisCache", settings.CACHES["default"]["BACKEND"])
        cache.set("cache_regression_key", "ok", timeout=60)
        self.assertEqual(cache.get("cache_regression_key"), "ok")

    def test_optimized_results_receiver_accepts_log_chunks(self):
        request = self.factory.post(
            "/odozi/results/",
            data={"tool": "pytest", "repo": "owner/repo", "run_id": "run-1", "logs": ["line 1", "line 2"]},
            format="json",
        )

        with patch("odozi.views.boto3.client") as mocked_client, patch("odozi.views.AuditWorkflow.objects.filter") as mocked_filter:
            mocked_filter.return_value.order_by.return_value.first.return_value = None
            response = OptimizedResultsReceiverView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        response.render()
        payload = json.loads(response.content)
        self.assertEqual(payload["status"], "ignored")
        mocked_client.assert_not_called()

import uuid
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from general.models import AuditJob
from general.views import CloudinaryHistoryReportView


class AuditJobResultTests(TestCase):
    def test_pipeline_can_store_multiple_tool_reports(self):
        pipeline_id = uuid.uuid4()
        AuditJob.objects.create(pipeline_id=pipeline_id)  # pipeline summary
        for tool, run_id in (("pytest", "101"), ("bandit", "102"), ("ruff", "103")):
            AuditJob.objects.create(
                pipeline_id=pipeline_id,
                tool_name=tool,
                run_id=run_id,
                log_blob_path=f"https://example.test/{tool}.json",
            )

        reports = AuditJob.objects.filter(
            pipeline_id=pipeline_id,
            log_blob_path__isnull=False,
        ).exclude(log_blob_path="")
        self.assertEqual(reports.count(), 3)

    @patch("general.views.requests.get")
    def test_history_endpoint_returns_every_report(self, mock_get):
        pipeline_id = uuid.uuid4()
        for tool, run_id in (("pytest", "101"), ("bandit", "102"), ("ruff", "103")):
            AuditJob.objects.create(
                pipeline_id=pipeline_id,
                tool_name=tool,
                run_id=run_id,
                log_blob_path=f"https://example.test/{tool}.json",
            )
        mock_get.side_effect = [
            Mock(status_code=200, json=lambda tool=tool: {"tool": tool})
            for tool in ("pytest", "bandit", "ruff")
        ]

        response = CloudinaryHistoryReportView.as_view()(
            APIRequestFactory().get(f"/general/cloudinary-report/{pipeline_id}/"),
            pipeline_id=str(pipeline_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual([item["tool"] for item in response.data["reports"]], ["pytest", "bandit", "ruff"])

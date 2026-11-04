import json

from django.test import SimpleTestCase

from agents.guardrails import check_orchestrator_action
from agents.judging import (
    compact_judge_evidence,
    compact_task_results,
    format_quality_note,
    has_failed_results,
)


class NeMoOrchestratorGuardrailTests(SimpleTestCase):
    def run_guardrail(self, action, current_request):
        return check_orchestrator_action(
            current_request=current_request,
            action_json=json.dumps(action),
        )

    def test_analysis_is_allowed_only_with_explicit_repository_and_branch(self):
        action = {
            "intents": ["run_static_analysis"],
            "active_rules": [
                {"repo_name": "odozi", "target_branch": "main", "strategies": {"pytest": {}}}
            ],
        }

        allowed = self.run_guardrail(
            action,
            "Run pytest on odozi using the main branch.",
        )
        blocked = self.run_guardrail(
            action,
            "Run pytest on odozi.",
        )

        self.assertEqual(getattr(allowed.status, "value", allowed.status), "passed")
        self.assertEqual(getattr(blocked.status, "value", blocked.status), "blocked")

    def test_workspace_deletion_requires_current_explicit_request_and_target(self):
        action = {
            "intents": ["delete_workspace"],
            "workspaces_to_delete": [{"workspace_name": "oluchi"}],
        }

        allowed = self.run_guardrail(action, "Delete the oluchi workspace.")
        blocked = self.run_guardrail(
            action,
            "What workspaces do I have?",
        )
        negated = self.run_guardrail(
            action,
            "Do not delete the oluchi workspace.",
        )

        self.assertEqual(getattr(allowed.status, "value", allowed.status), "passed")
        self.assertEqual(getattr(blocked.status, "value", blocked.status), "blocked")
        self.assertEqual(getattr(negated.status, "value", negated.status), "blocked")

    def test_workspace_key_deletion_requires_explicit_all_keys_request(self):
        action = {
            "intents": ["delete_repo_env"],
            "env_keys_to_delete": [
                {"delete_which": "workspace", "workspace_name": "oluchi"}
            ],
        }

        allowed = self.run_guardrail(
            action,
            "Delete all environment keys in the oluchi workspace.",
        )
        blocked = self.run_guardrail(
            action,
            "Delete environment keys in the oluchi workspace.",
        )

        self.assertEqual(getattr(allowed.status, "value", allowed.status), "passed")
        self.assertEqual(getattr(blocked.status, "value", blocked.status), "blocked")


class FollowUpJudgeEvidenceTests(SimpleTestCase):
    def test_failure_detection_checks_nested_statuses(self):
        self.assertTrue(
            has_failed_results(
                [{"status": "success"}, {"result": {"scope_status": "failure"}}]
            )
        )
        self.assertFalse(has_failed_results([{"status": "success"}]))

    def test_compacted_evidence_omits_logs_and_secrets(self):
        results = [
            {
                "status": "failed",
                "message": (
                    'pytest failed; token=do-not-send api_key=also-secret '
                    '"client_secret": "quoted-secret"'
                ),
                "raw_terminal_stdout_stream": "very long output",
                "github_token": "do-not-send",
            }
        ]

        compacted_results = compact_task_results(results)
        judge_evidence = compact_judge_evidence(results, "The tests failed.")

        self.assertIn("pytest failed", compacted_results)
        self.assertNotIn("very long output", compacted_results)
        self.assertNotIn("do-not-send", compacted_results)
        self.assertNotIn("also-secret", compacted_results)
        self.assertNotIn("quoted-secret", compacted_results)
        self.assertLessEqual(len(judge_evidence), 6000)

    def test_compacted_task_results_respect_requested_size_limit(self):
        oversized = [{"status": "failed", "message": "x" * 350} for _ in range(10)]

        self.assertLessEqual(len(compact_task_results(oversized, max_chars=100)), 100)

    def test_quality_note_reports_review_status(self):
        note = format_quality_note(
            {
                "status": "needs_review",
                "score": 2,
                "rationale": "The report overstated the outcome.",
                "issues": ["A failed check was omitted."],
            }
        )

        self.assertIn("needs review (2/5)", note)
        self.assertIn("failed check was omitted", note)

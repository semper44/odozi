from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from agents.evals.evaluation import (
    DEFAULT_DATASET_PATH,
    evaluate_expectations,
    load_dataset,
)


class PromptEvaluationTests(SimpleTestCase):
    def test_orchestrator_dataset_is_valid_and_has_unique_cases(self):
        cases = load_dataset(DEFAULT_DATASET_PATH)

        self.assertGreaterEqual(len(cases), 4)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))

    def test_dataset_rejects_duplicate_case_ids(self):
        with TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "dataset.json"
            dataset.write_text(
                '[{"id":"same","input":"first","assertions":{}},'
                '{"id":"same","input":"second","assertions":{}}]',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Duplicate evaluation case id"):
                load_dataset(dataset)

    def test_dataset_rejects_non_array_root(self):
        with TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "dataset.json"
            dataset.write_text('{"id":"not-an-array"}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must contain a JSON array"):
                load_dataset(dataset)

    def test_expectations_check_nested_structured_output(self):
        output = {
            "intents": ["run_static_analysis"],
            "active_rules": [
                {
                    "target_branch": "master",
                    "strategies": {"pytest": {}},
                }
            ],
        }

        failures = evaluate_expectations(
            output,
            {
                "equals": {"active_rules.0.target_branch": "master"},
                "contains": {"active_rules.0.strategies": ["pytest"]},
                "empty": [],
            },
        )

        self.assertEqual(failures, [])

    def test_expectations_report_mismatched_values(self):
        failures = evaluate_expectations(
            {"intents": ["technical_query"], "active_rules": []},
            {
                "equals": {"intents": ["run_static_analysis"]},
                "empty": ["active_rules"],
            },
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("intents", failures[0])

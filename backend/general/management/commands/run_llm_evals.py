from pathlib import Path

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback

from agents.evals.evaluation import (
    DEFAULT_DATASET_PATH,
    evaluate_expectations,
    load_dataset,
)
from django_python.schema import OrchestratorAction
from odozi.telemetry import llm_call, record_llm_tokens


class Command(BaseCommand):
    help = "Run the versioned prompt regression dataset against a live LLM."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            required=True,
            choices=("openai", "google"),
            help="The provider to use for these live evaluation calls.",
        )
        parser.add_argument(
            "--model",
            required=True,
            help="The provider model name to evaluate.",
        )
        parser.add_argument(
            "--dataset",
            type=Path,
            default=DEFAULT_DATASET_PATH,
            help="JSON evaluation dataset (defaults to the orchestrator dataset).",
        )

    def handle(self, *args, **options):
        from agents.tasks import system_instruction_text

        dataset_path = options["dataset"]
        try:
            cases = load_dataset(dataset_path)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        if options["provider"] == "openai":
            api_key = config("OPENAI_API_KEY", default="")
            if not api_key:
                raise CommandError("OPENAI_API_KEY is required for OpenAI evaluations.")
            model = ChatOpenAI(
                model=options["model"],
                temperature=0,
                api_key=api_key,
            )
        else:
            gemini_api_key = settings.GEMINI_API_KEY
            if not isinstance(gemini_api_key, str) or not gemini_api_key.strip():
                raise CommandError("GEMINI_API_KEY is required for Google evaluations.")
            model = ChatGoogleGenerativeAI(
                model=options["model"],
                temperature=0,
                google_api_key=gemini_api_key,
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_instruction_text),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )
        chain = prompt | model.with_structured_output(OrchestratorAction)

        passed = 0
        for case in cases:
            with llm_call(
                "prompt_regression",
                options["provider"],
                options["model"],
            ) as llm_span:
                with get_openai_callback() as callback:
                    output = chain.invoke({"history": [], "input": case["input"]})
                record_llm_tokens(
                    llm_span,
                    options["provider"],
                    options["model"],
                    callback.prompt_tokens,
                    callback.completion_tokens,
                )
            failures = evaluate_expectations(output, case["assertions"])
            if failures:
                self.stderr.write(self.style.ERROR(f"FAIL {case['id']}"))
                for failure in failures:
                    self.stderr.write(f"  - {failure}")
            else:
                passed += 1
                self.stdout.write(self.style.SUCCESS(f"PASS {case['id']}"))

        failed = len(cases) - passed
        self.stdout.write(f"Evaluation result: {passed}/{len(cases)} passed.")
        if failed:
            raise CommandError(f"{failed} prompt regression case(s) failed.")

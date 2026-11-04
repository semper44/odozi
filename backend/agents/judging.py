import json
import re
from collections.abc import Mapping
from typing import Any


FAILURE_STATUSES = {
    "error",
    "failed",
    "failure",
    "partial_failure",
    "timeout",
    "validation_error",
}
SENSITIVE_OR_BULKY_KEYS = {
    "api_key",
    "authorization",
    "cloudinary_url",
    "credential",
    "credentials",
    "full_report_url",
    "log_blob_path",
    "logs",
    "password",
    "pipeline_id",
    "raw_output",
    "raw_payload",
    "raw_terminal_stdout_stream",
    "secret",
    "stack_trace",
    "stderr",
    "stdout",
    "token",
    "traceback",
}
MAX_RESULT_TEXT_CHARS = 350
MAX_REPORT_EVIDENCE_CHARS = 6000
MAX_TASK_RESULTS = 20
SECRET_TEXT_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(
        r"(?i)['\"]?\b(?:[a-z0-9]+[_ -])*(?:api[_ -]?key|access[_ -]?token|"
        r"password|secret|token|credential|private[_ -]?key)[a-z0-9_-]*\b"
        r"['\"]?(\s*[:=]\s*)['\"]?[^\s,;'\"}]+"
    ),
)
SENSITIVE_KEY_PARTS = (
    "accesskey",
    "apikey",
    "authorization",
    "credential",
    "password",
    "privatekey",
    "secret",
    "token",
)


def has_failed_results(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key.casefold() in {"status", "scope_status"} and isinstance(child, str):
                if child.casefold() in FAILURE_STATUSES:
                    return True
            if key.casefold() in {"error", "exception"} and child:
                return True
            if has_failed_results(child):
                return True
    elif isinstance(value, list):
        return any(has_failed_results(item) for item in value)
    return False


def _compact_value(value: Any, depth: int = 0) -> Any:
    if depth >= 4:
        return "[details omitted]"
    if isinstance(value, Mapping):
        return {
            str(key): _compact_value(child, depth + 1)
            for key, child in list(value.items())[:30]
            if str(key).casefold() not in SENSITIVE_OR_BULKY_KEYS
            and not any(
                marker in str(key).casefold().replace("_", "").replace("-", "")
                for marker in SENSITIVE_KEY_PARTS
            )
        }
    if isinstance(value, list):
        return [_compact_value(item, depth + 1) for item in value[:8]]
    if isinstance(value, str):
        for pattern in SECRET_TEXT_PATTERNS:
            value = pattern.sub("[redacted]", value)
        return value[:MAX_RESULT_TEXT_CHARS]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_RESULT_TEXT_CHARS]


def compact_task_results(task_results: Any, max_chars: int = 12000) -> str:
    """Keep useful result summaries while excluding logs, credentials, and blobs."""
    results = task_results if isinstance(task_results, list) else [task_results]
    compacted = [_compact_value(item) for item in results[:MAX_TASK_RESULTS]]
    if len(results) > MAX_TASK_RESULTS:
        compacted.append({"omitted_result_count": len(results) - MAX_TASK_RESULTS})

    encoded = json.dumps(compacted, indent=2, ensure_ascii=True)
    if len(encoded) <= max_chars:
        return encoded

    compacted = compacted[: max(1, MAX_TASK_RESULTS // 2)]
    omitted_marker = {"message": "Additional result details omitted due to size."}
    while compacted and len(
        json.dumps(compacted + [omitted_marker], indent=2, ensure_ascii=True)
    ) > max_chars:
        compacted.pop()

    encoded = json.dumps(compacted + [omitted_marker], indent=2, ensure_ascii=True)
    if len(encoded) <= max_chars:
        return encoded
    minimal = json.dumps({"message": "Task details omitted due to size."})
    return minimal if len(minimal) <= max_chars else "[]"


def compact_judge_evidence(task_results: Any, report: str) -> str:
    task_summary = compact_task_results(
        task_results,
        max_chars=MAX_REPORT_EVIDENCE_CHARS // 2,
    )
    evidence = {
        "task_results": task_summary,
        "assistant_report": _compact_value(report)[:1600],
    }
    encoded = json.dumps(evidence, indent=2, ensure_ascii=True)
    return encoded[:MAX_REPORT_EVIDENCE_CHARS]


def format_quality_note(evaluation: Mapping[str, Any]) -> str:
    status = evaluation.get("status")
    if status == "not_run":
        return "Quality check: not run because no task failures were reported."
    if status == "error":
        return "Quality check: unavailable; the generated report was not independently checked."

    score = evaluation.get("score")
    score_text = f" ({score}/5)" if isinstance(score, int) else ""
    if status == "passed":
        return f"Quality check: passed{score_text}."

    rationale = _compact_value(evaluation.get("rationale", ""))
    note = f"Quality check: needs review{score_text}."
    if isinstance(rationale, str) and rationale:
        note += f" {rationale}"
    issues = evaluation.get("issues")
    if isinstance(issues, list):
        safe_issues = [
            _compact_value(issue)
            for issue in issues[:3]
            if isinstance(issue, str) and issue
        ]
        if safe_issues:
            note += " Issues: " + "; ".join(safe_issues)
    return note

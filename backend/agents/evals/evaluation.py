import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


DEFAULT_DATASET_PATH = Path(__file__).with_name("orchestrator.json")
SUPPORTED_ASSERTIONS = {"equals", "contains", "empty"}


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as dataset_file:
            data = json.load(dataset_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path} at line {exc.lineno}: {exc.msg}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Evaluation dataset {path} must contain a JSON array.")

    seen_ids: set[str] = set()
    for index, case in enumerate(data):
        case_number = index + 1
        if not isinstance(case, dict):
            raise ValueError(
                f"Evaluation case {case_number} in {path} must be a JSON object."
            )
        case_id = case.get("id")
        prompt = case.get("input")
        assertions = case.get("assertions")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(
                f"Evaluation case {case_number} in {path} needs a non-empty id."
            )
        if case_id in seen_ids:
            raise ValueError(f"Duplicate evaluation case id {case_id!r} in {path}.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(
                f"Evaluation case {case_id!r} needs a non-empty input prompt."
            )
        if not isinstance(assertions, dict) or set(assertions) - SUPPORTED_ASSERTIONS:
            raise ValueError(
                f"Evaluation case {case_id!r} has invalid assertions; "
                f"supported assertions are {sorted(SUPPORTED_ASSERTIONS)}."
            )

        for name in ("equals", "contains"):
            if name in assertions and not isinstance(assertions[name], dict):
                raise ValueError(
                    f"Evaluation case {case_id!r}: {name!r} must be an object."
                )
        if "equals" in assertions and not all(
            isinstance(path, str) and path for path in assertions["equals"]
        ):
            raise ValueError(
                f"Evaluation case {case_id!r}: equality paths must be non-empty strings."
            )
        if "contains" in assertions and any(
            not isinstance(path, str)
            or not path
            or not isinstance(expected, list)
            for path, expected in assertions["contains"].items()
        ):
            raise ValueError(
                f"Evaluation case {case_id!r}: contains assertions must map "
                "non-empty paths to lists."
            )
        if "empty" in assertions and (
            not isinstance(assertions["empty"], list)
            or not all(isinstance(item, str) and item for item in assertions["empty"])
        ):
            raise ValueError(
                f"Evaluation case {case_id!r}: 'empty' must be a list of "
                "non-empty paths."
            )

        seen_ids.add(case_id)

    if not data:
        raise ValueError(f"Evaluation dataset {path} contains no cases.")
    return data


def _resolve_path(data: Any, path: str) -> Any:
    value = data
    for part in path.split("."):
        if isinstance(value, Mapping):
            if part not in value:
                raise KeyError(f"Missing field {part!r} while resolving {path!r}.")
            value = value[part]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            try:
                value = value[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(f"Invalid sequence index {part!r} in {path!r}.") from exc
        else:
            raise KeyError(f"Cannot resolve {part!r} in {path!r}.")
    return value


def evaluate_expectations(output: Any, assertions: dict[str, Any]) -> list[str]:
    if hasattr(output, "model_dump"):
        output = output.model_dump(mode="json")
    if not isinstance(output, Mapping):
        raise TypeError("Evaluation output must be a mapping or a Pydantic model.")

    failures: list[str] = []
    for path, expected in assertions.get("equals", {}).items():
        try:
            actual = _resolve_path(output, path)
        except KeyError as exc:
            failures.append(str(exc))
            continue
        if actual != expected:
            failures.append(f"{path}: expected {expected!r}, got {actual!r}.")

    for path, expected in assertions.get("contains", {}).items():
        try:
            actual = _resolve_path(output, path)
        except KeyError as exc:
            failures.append(str(exc))
            continue
        if isinstance(actual, Mapping):
            missing = [item for item in expected if item not in actual]
        elif isinstance(actual, Sequence) and not isinstance(actual, (str, bytes)):
            missing = [item for item in expected if item not in actual]
        else:
            failures.append(f"{path}: expected a mapping or sequence, got {type(actual).__name__}.")
            continue
        if missing:
            failures.append(f"{path}: expected to contain {missing!r}.")

    for path in assertions.get("empty", []):
        try:
            actual = _resolve_path(output, path)
        except KeyError as exc:
            failures.append(str(exc))
            continue
        if actual not in ([], {}, "", None):
            failures.append(f"{path}: expected an empty value, got {actual!r}.")

    return failures

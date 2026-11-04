import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


GUARDRAILS_CONFIG_PATH = Path(__file__).with_name("guardrails")
ALLOWED_INTENTS = {
    "technical_query",
    "run_static_analysis",
    "create_workspace",
    "delete_workspace",
    "create_repo_env",
    "delete_repo_env",
}
INTENT_VERBS = {
    "run_static_analysis": re.compile(r"\b(run|execute|launch|start)\b", re.IGNORECASE),
    "create_workspace": re.compile(r"\b(create|make|new|group)\b", re.IGNORECASE),
    "delete_workspace": re.compile(r"\b(delete|remove|drop)\b", re.IGNORECASE),
    "create_repo_env": re.compile(r"\b(create|add|set|configure)\b", re.IGNORECASE),
    "delete_repo_env": re.compile(r"\b(delete|remove|drop|clear)\b", re.IGNORECASE),
}
NEGATED_OPERATION_PREFIX = re.compile(
    r"\b(?:do\s+not|don't|never|avoid|should\s+not|shouldn't|must\s+not|mustn't|no\s+need\s+to)"
    r"\s+(?:\w+\s+){0,3}$",
    re.IGNORECASE,
)


def _has_authorizing_verb(intent: str, current_request: str) -> bool:
    for match in INTENT_VERBS[intent].finditer(current_request):
        prefix = current_request[max(0, match.start() - 48):match.start()]
        if not NEGATED_OPERATION_PREFIX.search(prefix):
            return True
    return False


def _contains_named_target(text: str, target: str) -> bool:
    normalized_target = target.strip()
    if not normalized_target:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_target)}(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _validate_structured_action(
    action_data: dict[str, Any],
    current_request: str,
) -> list[str]:
    violations: list[str] = []
    intents = action_data.get("intents")
    if not isinstance(intents, list) or not all(isinstance(item, str) for item in intents):
        return ["The action must contain a list of intent names."]

    unsupported = sorted(set(intents) - ALLOWED_INTENTS)
    if unsupported:
        violations.append(f"Unsupported intent(s): {', '.join(unsupported)}.")

    requested_operation = {
        intent: _has_authorizing_verb(intent, current_request)
        for intent in INTENT_VERBS
    }

    for intent in INTENT_VERBS:
        if intent in intents and not requested_operation[intent]:
            violations.append(
                f"The current request does not explicitly authorize {intent}."
            )

    if "run_static_analysis" in intents:
        rules = action_data.get("active_rules")
        if not isinstance(rules, list) or not rules:
            violations.append("Analysis execution has no selected repository rules.")
        else:
            for rule in rules:
                if not isinstance(rule, dict):
                    violations.append("An analysis rule is not a valid object.")
                    continue
                repository = rule.get("repo_name")
                branch = rule.get("target_branch")
                if not isinstance(repository, str) or not _contains_named_target(
                    current_request, repository
                ):
                    violations.append(
                        "Analysis targets a repository not named in the current request."
                    )
                if not isinstance(branch, str) or not _contains_named_target(
                    current_request, branch
                ):
                    violations.append(
                        "Analysis requires a branch explicitly named in the current request."
                    )

    if "create_workspace" in intents:
        workspaces = action_data.get("workspaces_to_create")
        if not isinstance(workspaces, list) or not workspaces:
            violations.append("Workspace creation needs a named workspace and repositories.")
        else:
            for workspace in workspaces:
                if not isinstance(workspace, dict):
                    violations.append("A workspace creation target is invalid.")
                    continue
                name = workspace.get("new_workspace_name")
                repositories = workspace.get("repositories")
                if not isinstance(name, str) or not _contains_named_target(
                    current_request, name
                ):
                    violations.append(
                        "Workspace creation targets a name not mentioned in the current request."
                    )
                if not isinstance(repositories, list) or not repositories:
                    violations.append(
                        "Workspace creation needs at least one explicitly named repository."
                    )
                elif any(
                    not isinstance(repo, str)
                    or not _contains_named_target(current_request, repo)
                    for repo in repositories
                ):
                    violations.append(
                        "Workspace creation includes a repository not named in the current request."
                    )

    if "create_repo_env" in intents:
        requests = action_data.get("env_keys_to_create")
        if not isinstance(requests, list) or not requests:
            violations.append("Environment-key creation needs a named scope and key.")
        else:
            for request in requests:
                if not isinstance(request, dict):
                    violations.append("An environment-key creation target is invalid.")
                    continue
                workspace_name = request.get("workspace_name")
                repositories = request.get("repositories", [])
                key_names = request.get("key_names")
                if not isinstance(key_names, list) or not key_names:
                    violations.append("Environment-key creation needs at least one named key.")
                elif any(
                    not isinstance(key, str)
                    or not _contains_named_target(current_request, key)
                    for key in key_names
                ):
                    violations.append(
                        "Environment-key creation includes a key not named in the current request."
                    )
                if workspace_name is not None:
                    if (
                        repositories
                        or not isinstance(workspace_name, str)
                        or not _contains_named_target(current_request, workspace_name)
                    ):
                        violations.append(
                            "Workspace environment-key creation needs its named workspace only."
                        )
                elif (
                    not isinstance(repositories, list)
                    or not repositories
                    or any(
                        not isinstance(repo, str)
                        or not _contains_named_target(current_request, repo)
                        for repo in repositories
                    )
                ):
                    violations.append(
                        "Repository environment-key creation needs explicitly named repositories only."
                    )

    if "delete_workspace" in intents:
        workspaces = action_data.get("workspaces_to_delete", [])
        if not requested_operation.get("delete_workspace"):
            violations.append("Workspace deletion needs an explicit deletion request.")
        if not isinstance(workspaces, list) or not workspaces:
            violations.append("Workspace deletion needs a named target.")
        else:
            for workspace in workspaces:
                name = workspace.get("workspace_name") if isinstance(workspace, dict) else None
                if not isinstance(name, str) or not _contains_named_target(current_request, name):
                    violations.append(
                        "Workspace deletion targets a name not mentioned by the user."
                    )

    if "delete_repo_env" in intents:
        requests = action_data.get("env_keys_to_delete", [])
        if not requested_operation.get("delete_repo_env"):
            violations.append("Environment-key deletion needs an explicit deletion request.")
        if not isinstance(requests, list) or not requests:
            violations.append("Environment-key deletion needs an explicit target scope.")
        else:
            for request in requests:
                if not isinstance(request, dict):
                    violations.append("An environment-key deletion target is invalid.")
                    continue
                scope = request.get("delete_which")
                workspace_name = request.get("workspace_name")
                repositories = request.get("repositories", [])
                if scope == "workspace":
                    if repositories or not isinstance(workspace_name, str) or not _contains_named_target(
                        current_request, workspace_name
                    ):
                        violations.append(
                            "Workspace environment-key deletion needs its named workspace only."
                        )
                    if not re.search(
                        r"\b(all|every)\b",
                        current_request,
                        re.IGNORECASE,
                    ):
                        violations.append(
                            "Workspace-scope deletion removes every key and needs an explicit all-keys request."
                        )
                elif scope == "repo":
                    if workspace_name is not None or not isinstance(repositories, list) or not repositories:
                        violations.append(
                            "Repository environment-key deletion needs named repositories only."
                        )
                    elif any(
                        not isinstance(repo, str)
                        or not _contains_named_target(current_request, repo)
                        for repo in repositories
                    ):
                        violations.append(
                            "Repository environment-key deletion targets a name not mentioned by the user."
                        )
                    if not re.search(
                        r"\b(all|every)\b",
                        current_request,
                        re.IGNORECASE,
                    ):
                        violations.append(
                            "Repository-scope deletion removes every key and needs an explicit all-keys request."
                        )
                elif scope == "key_names":
                    key_names = request.get("key_names", [])
                    if not isinstance(key_names, list):
                        violations.append("Environment-key names must be a list.")
                    elif not key_names:
                        violations.append(
                            "Key-name deletion needs at least one exact key name."
                        )
                    elif key_names and any(
                        not isinstance(key, str)
                        or not _contains_named_target(current_request, key)
                        for key in key_names
                    ):
                        violations.append(
                            "Environment-key deletion targets a key not mentioned by the user."
                        )
                    if workspace_name is not None and (
                        repositories
                        or not isinstance(workspace_name, str)
                        or not _contains_named_target(current_request, workspace_name)
                    ):
                        violations.append(
                            "Key-name deletion has an invalid workspace scope."
                        )
                    if repositories and (
                        workspace_name is not None
                        or not isinstance(repositories, list)
                        or any(
                            not isinstance(repo, str)
                            or not _contains_named_target(current_request, repo)
                            for repo in repositories
                        )
                    ):
                        violations.append(
                            "Key-name deletion has an invalid repository scope."
                        )
                else:
                    violations.append("Environment-key deletion has an unsupported scope.")

    return violations


def validate_orchestrator_action(action_json: str) -> dict[str, Any]:
    """NeMo custom action that blocks invalid or unconfirmed operational actions."""
    try:
        envelope = json.loads(action_json)
    except (TypeError, json.JSONDecodeError):
        return {"is_blocked": True, "reason": "The orchestration output was not valid JSON."}

    if not isinstance(envelope, dict):
        return {"is_blocked": True, "reason": "The orchestration output had an invalid shape."}

    action_data = envelope.get("action")
    current_request = envelope.get("current_request", "")
    if not isinstance(action_data, dict):
        return {"is_blocked": True, "reason": "The action payload had an invalid shape."}
    if not isinstance(current_request, str):
        return {"is_blocked": True, "reason": "The request context had an invalid shape."}

    violations = _validate_structured_action(
        action_data,
        current_request,
    )
    return {
        "is_blocked": bool(violations),
        "reason": " ".join(violations),
    }


@lru_cache(maxsize=1)
def _get_rails():
    from nemoguardrails import LLMRails, RailsConfig

    config = RailsConfig.from_path(str(GUARDRAILS_CONFIG_PATH))
    rails = LLMRails(config)
    rails.register_action(
        validate_orchestrator_action,
        name="validate_orchestrator_action",
    )
    return rails


def check_orchestrator_action(
    current_request: str,
    action_json: str,
):
    """Run the configured NeMo output rail without invoking the app's LLM chain."""
    try:
        action_data = json.loads(action_json)
    except json.JSONDecodeError as exc:
        raise ValueError("The orchestration output was not valid JSON.") from exc
    rails = _get_rails()
    envelope = json.dumps(
        {
            "action": action_data,
            "current_request": current_request,
        },
        ensure_ascii=True,
    )
    from nemoguardrails.rails.llm.options import RailType

    return rails.check(
        [{"role": "assistant", "content": envelope}],
        rail_types=[RailType.OUTPUT],
    )

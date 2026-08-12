import os
import re
import uuid
import httpx
import json
import time
import jwt
import base64
import shutil
import inspect
import requests
import traceback
import subprocess
import textwrap
from toon import encode
from typing import Any, Dict, List, cast

from celery import shared_task, group, chord, signature

from .custom_functions.rules_registry import AST_TOOL_REGISTRY
from .custom_functions import rule_classes

from account_profile.models import GitHubRepository, UserProfileModel, Workspace
from django_python.schema import OrchestratorAction 

from odozi.service import (create_workspace_with_repos, get_installation_access_token, 
                           create_repo_env_keys_service,delete_repo_env_keys_service,  
                           delete_workspace_with_repos
)


from django.conf import settings
from django.db import transaction
from django.core.cache import cache
from django.contrib.auth.models import User
from django.db.utils import OperationalError

from django_python.models import RepositoryScan, RepoEnvKey,ChatSession, ChatMessage
from django_python.schema import OrchestratorAction

from concurrent.futures import ThreadPoolExecutor
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


# LangChain Drivers
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_community.callbacks import get_openai_callback 


# Celery tasks (the parallel tools)

UNIVERSAL_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout
)

error_data = {}

def transform_ci_results(raw_results):
    """
    Transforms raw JSON outputs from Ruff, Bandit, and Semgrep 
    into a standardized, highly readable format.
    """
    simplified_report = {
        "summary": {"total_issues": 0, "passed_tools": [], "failed_tools": []},
        "violations": []
    }

    for report in raw_results:
        tool_name = report.get("tool")
        status = report.get("status")

        if status == "passed":
            simplified_report["summary"]["passed_tools"].append(tool_name)
            continue
        
        simplified_report["summary"]["failed_tools"].append(tool_name)

        # --- TRANSFORM LINTER (RUFF) ---
        if tool_name == "linter":
            errors = report.get("errors_found", [])
            # If the errors are still an unparsed JSON string, load them
            if isinstance(errors, str) and errors.strip():
                try:
                    errors = json.loads(errors)
                except:
                    errors = []
            
            for err in errors:
                simplified_report["violations"].append({
                    "tool": "Ruff Linter",
                    "file": err.get("filename", "").split("/app/")[-1], # Clean path
                    "line": err.get("location", {}).get("row"),
                    "severity": err.get("severity", "STYLE"),
                    "message": err.get("message", ""),
                    "rule_id": err.get("code", "")
                })

        # --- TRANSFORM SECURITY SCAN (BANDIT) ---
        elif tool_name == "security_scan":
            vulns = report.get("vulnerabilities", [])
            if isinstance(vulns, str) and vulns.strip():
                try:
                    vulns = json.loads(vulns).get("results", [])
                except:
                    vulns = []

            for vuln in vulns:
                simplified_report["violations"].append({
                    "tool": "Bandit Security",
                    "file": vuln.get("filename", ""),
                    "line": vuln.get("line_number"),
                    "severity": vuln.get("issue_severity", "HIGH"),
                    "message": vuln.get("issue_text", ""),
                    "rule_id": vuln.get("test_id", "")
                })

       
        # --- TRANSFORM SECRET SCANNER ---
        elif tool_name == "secret_scanner":
            leaks = report.get("leaked_secrets", {})
            for filepath, details in leaks.items():
                for leakage_meta in details:
                    simplified_report["violations"].append({
                        "tool": "Secret Scanner",
                        "file": filepath,
                        "line": leakage_meta.get("line_number"),
                        "severity": "CRITICAL",
                        "message": f"Potential leaked credential hash type: {leakage_meta.get('type')}",
                        "rule_id": "hardcoded-secret"
                    })


       
         # --- TRANSFORM MYPY ---        
        elif tool_name == "mypy_type_check":
            for err in report.get("type_errors", []):
                simplified_report["violations"].append({
                    "tool": "Odozi Type Hint Governance",
                    "file": err["file"],
                    "line": err["line"],
                    "severity": "TYPING_MISSING",
                    "message": f"In function '{err['function']}': {err['error']}",
                    "rule_id": "missing-type-hint"
                })

        # --- TRANSFORM CUSTOM MIGRATION CHECK ---
        elif tool_name == "migration_consistency":
            for violation in report.get("violations", []):
                simplified_report["violations"].append({
                    "tool": "Odozi Migration Guardrail",
                    "file": f"{violation['app']}/models.py",
                    "line": 1,
                    "severity": "SCHEMA_MISMATCH",
                    "message": violation["message"],
                    "rule_id": "missing-migration-file"
                })

        # --- TRANSFORM CUSTOM GUARDRAILS (SEMGREP) ---
        elif tool_name == "semgrep_custom":
            findings = report.get("findings", [])
            for finding in findings:
                extra = finding.get("extra", {})
                simplified_report["violations"].append({
                    "tool": "Odozi Custom Guardrail",
                    "file": finding.get("path", ""),
                    "line": finding.get("start", {}).get("line"),
                    "severity": extra.get("severity", "ERROR"),
                    "message": extra.get("message", ""),
                    "rule_id": finding.get("check_id", "")
                })

    simplified_report["summary"]["total_issues"] = len(simplified_report["violations"])
    return simplified_report



def extract_test_coverage(path):
    coverage_file = os.path.join(path, "coverage.json")
    if not os.path.exists(coverage_file):
        return {"status": "error", "message": "Coverage file missing"}

    with open(coverage_file, "r") as f:
        data = json.load(f)

    # Pull the exact mathematical coverage percentage totals out of the file
    total_coverage = data.get("totals", {}).get("percent_covered", 0)
    
    return {
        "tool": "pytest_coverage",
        "status": "passed" if total_coverage >= 80.0 else "failed",
        "coverage_percentage": round(total_coverage, 2),
        "summary": f"Codebase tracking achieved {round(total_coverage, 2)}% statement execution coverage"
    }




user_payload = {
    "constraints": [
        # Check 1: Must call transaction.atomic
        {
            "type": "check_required_call",
            "params": {"keyword": "payment", "required_call": "transaction.atomic"}
        },
        # Check 2: Must call select_related
        {
            "type": "check_required_call",
            "params": {"keyword": "payment", "required_call": "select_related"}
        },
        # Check 3: Must call prefetch_related
        {
            "type": "check_required_call",
            "params": {"keyword": "payment", "required_call": "prefetch_related"}
        },
        # Check 4: Line count limit on payment functions
        {
            "type": "check_function_length", # We will define this template below
            "params": {"keyword": "payment", "max_lines": 200}
        }
    ]
}




def find_matching_repos_from_redis(all_repos, user_provided_input, channel_name):
    """
    Finds all potential repository matches from Redis.
    Returns a list of unique, case-preserved GitHub repository names.
    """

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
            channel_name,
            {
                "type": "chat_message",
                "payload": {
                    "type": "orchestration_result",
                    "raw_output": {
                        "ui_layout_route": "CHAT",
                        "chat_response": "Matching Repos" ,
                    },
                }
            }
        )
    did_not_match_exactly = True
    raw_search = user_provided_input.strip().lower()
    # Strip symbols entirely to catch missing hyphens/underscores
    alphanumeric_search = "".join(c for c in raw_search if c.isalnum())

    # Using sets to ensure we don't accidentally return duplicate names
    matched_names = set()
    default_branch = set()

    for repo_tuple in all_repos:
        true_github_name = repo_tuple.get('name', '')
        default__redis_branch = repo_tuple.get('default_branch')
        
        true_name_lower = true_github_name.lower()
        true_alphanumeric = "".join(c for c in true_name_lower if c.isalnum())

        # Catch case-insensitive matches OR alphanumeric matches (handles missing hyphens)
        if true_name_lower == raw_search or true_alphanumeric == alphanumeric_search:
            matched_names.add(true_github_name)
            default_branch.add(default__redis_branch)
            did_not_match_exactly = False
            continue

        # Catch fuzzy substring matches (handles partial inputs like 'taskmaster' matching 'Taskmaster--')
        if raw_search in true_name_lower or alphanumeric_search in true_alphanumeric:
            matched_names.add(true_github_name)
            default_branch.add(default__redis_branch)

    print("disrespect", default_branch)
    # Convert back to a list to easily pass back to your LLM or user chat
    return {
        "matched_names":list(matched_names), 
        "default_branches": list(default_branch),
        "did_not_match_exactly": did_not_match_exactly
        }



def workflow_exists(url, headers, branch_name):
    """
    Checks if a workflow file exists on a specific branch and returns its SHA.
    """
    try:
        print("\n==============================")
        print("CHECKING WORKFLOW")
        print("Branch:", branch_name)
        print("GET URL:", url)

        response = requests.get(url, headers=headers, timeout=15)

        print("GET Status:", response.status_code)
        print("GET Response:")

        # Always expose HTTP details so callers (and LLM) can reason about failures
        http_status = response.status_code
        http_body = response.text

        if http_status == 200:
            try:
                data = response.json()
                sha = data.get("sha")
            except Exception:
                sha = None

            print("Workflow EXISTS")
            print("SHA:", sha)

            return {
                "exists": True,
                "sha": sha,
                "http_status": http_status,
                "http_body": http_body
            }

        elif http_status == 404:
            print("Workflow DOES NOT exist.")

            return {
                "exists": False,
                "sha": None,
                "http_status": http_status,
                "http_body": http_body
            }

        else:
            print("Unexpected status code.")
            return {
                "exists": False,
                "sha": None,
                "http_status": http_status,
                "http_body": http_body
            }

    except Exception as e:
        print(f"Error checking workflow status: {e}")
        return {
            "exists": False,
            "sha": None,
            "http_status": None,
            "http_body": None,
            "error": str(e)
        }


def ensure_orchestrator_yaml_is_online(
    repo_owner,
    repo_name,
    target_branch,
    git_token,
    all_repos,
    channel_name
):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
            channel_name,
            {
                "type": "chat_message",
                "payload": {
                    "type": "orchestration_result",
                    "raw_output": {
                        "ui_layout_route": "CHAT",
                        "chat_response": "Verifying Repo name and branch on github" ,
                    },
                }
            }
        )
    matching_results = find_matching_repos_from_redis(all_repos, repo_name, channel_name)
    resolved_repo = matching_results["matched_names"]
    did_not_match_exactly = matching_results["did_not_match_exactly"]

    print(f"Matching results: {matching_results}")

    if len(resolved_repo) == 0:
        error_data["repo_resolution_not_found"] = {
            "status": "failed",
            "repo":resolved_repo[0],
            "message": f"You typed '{repo_name}', but I couldn't find any matching repository."
        }

        return error_data
        

    if len(resolved_repo) > 1:
        error_data["repo_resolution"] = {
            "status": "failed",
            "repo":resolved_repo[0],
            "message": f"Multiple repositories matched your input. Which one did you mean?\n{matching_results}"
        }

        return error_data
    
    default_branch = matching_results["default_branches"][0]

    print("\n==============================")
    print("Repository:", resolved_repo[0])
    print("Default branch:", default_branch)
    print("Target branch:", target_branch)
    print("==============================")

    url = (
        f"https://api.github.com/repos/"
        f"{repo_owner}/{resolved_repo[0]}/contents/"
        f".github/workflows/orchestrator.yaml"
    )

    headers = {
        "Authorization": f"Bearer {git_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    yaml_file_path = os.path.join(
        settings.BASE_DIR,
        "agents",
        "orchestrator.yaml"
    )

    with open(yaml_file_path, "r", encoding="utf-8") as f:
        yaml_content = f.read()

    encoded_content = base64.b64encode(
        yaml_content.encode("utf-8")
    ).decode("utf-8")

    # Remove duplicates while preserving order
    branches_to_process = list(
        dict.fromkeys([default_branch, target_branch])
    )

    branches_outcomes = []
    errors = []

    for branch in branches_to_process:

        print(f"\n========== PROCESSING BRANCH: {branch} ==========")

        check_url = f"{url}?ref={branch}"

        result = workflow_exists(
            check_url,
            headers,
            branch
        )


        payload = {
            "message": "ci: synchronize Odozi workflow",
            "content": encoded_content,
            "branch": branch
        }

        # Existing file -> update
        if result.get("exists"):
            if result.get("sha"):
                payload["sha"] = result.get("sha")
            print("Updating existing workflow...")
        else:
            print("Creating workflow...")

        try:
            response = requests.put(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )

            outcome = {
                "branch": branch,
                "attempted_url": url,
                "workflow_check": result,
                "http_status": response.status_code,
                "http_body": response.text
            }
            branches_outcomes.append(outcome)

            print("PUT Status:", response.status_code)

            if response.status_code not in (200, 201):
                errors.append({"branch": branch, "status": response.status_code, "body": response.text})
            else:
                print(f"Successfully synchronized workflow on '{branch}'.")

        except Exception as e:
            err = {"branch": branch, "error": str(e)}
            errors.append(err)
            branches_outcomes.append({"branch": branch, "error": str(e)})

    print("mum-dad", error_data)

    if errors:
        error_data["repo_resolution"] = {
            "status": "partial_failure" if branches_outcomes else "failed",
        }
        for error_message in errors:
            print(f"5k---{error_message}")
            error_string = error_message.get('body')

            # Parse the string into a Python dictionary
            parsed_error_string = json.loads(error_string)

            # Extract just the message
            print("wwwwwwwwwwwwwwww", parsed_error_string)
            crash_error = parsed_error_string.get('message', None)
            crash_branch = error_message.get('branch')
            if crash_error:
                error_data["repo_resolution"]["message"] = f"Failed to synchronize workflow on branch - '{crash_branch}' for repo - '{resolved_repo[0]}', 'branch - {error_message['branch']}'. Error: {crash_error}"
                error_data["repo_resolution"]["repo"] = resolved_repo[0]
                error_data["repo_resolution"]["branch"] = crash_branch
                break


        print("mum-dad2", error_data)
        return error_data

    print("\nWorkflow synchronized successfully on all required branches.")
    if did_not_match_exactly:
        return {
            "status": "success",
            "repo": resolved_repo[0],
            "message": f"Successfully synchronized workflow. Matched '{repo_name}' to '{resolved_repo[0]}'.",
            "branches": target_branch
        }
    else:
        return {
            "status": "success",
            "repo": resolved_repo[0],
            "message": "Successfully synchronized workflow",
            "branches": target_branch
        }





system_instruction_text = """
You are the AI Orchestrator Core for Project Odozi, an autonomous agentic CI/CD gateway. Your sole objective is to intercept a user's natural language project description or request, parse their intentions, and convert them into structured configuration variables inside our Pydantic action schema.

### CRITICAL ID HANDLING & PLACEHOLDER RULES (NEVER REQUEST INT IDS FROM USERS)
1. For deletions or updates targeting existing items: Look for the target item by its string name (e.g., 'zugo', 'semper') in the text prompt or conversation history records. 
2. Do NOT stop the process or complain about missing IDs. Let the backend service look up the record matching the provided string names instead.

### REGISTERED SYSTEM TOOL STRATEGIES & CROSS-CUTTING BUNDLES

When a user requests analysis, you must cross-reference their keywords to populate the 'active_rules' array with the exact matching strategies defined below. 

1. PILAR A: CODE SECURITY AUDITING
- Keywords: "security", "vulnerability", "audit", "owasp", "leak", "secret", "credentials"
- Trigger Rules: If any security keyword is mentioned, you MUST add BOTH "bandit" (for code flaws) AND "pii_leakage" (for logger file data leaks) to the active_rules array list. 

2. PILLAR B: DEPENDENCY INTEGRITY (NEW)
- Keywords: "dependencies", "packages", "requirements", "requirements.txt", "outdated packages", "vulnerable packages"
- Trigger Rules: If the user mentions packages or dependencies, assign the strategy "pip_audit". If they ask for a complete security check, bundle "pip_audit" alongside your Pillar A tools.

3. PILLAR C: CODE QUALITY & MAINTENANCE COMPLEXITY
- Keywords: "lint", "code smell", "clean code", "formatting", "complexity", "nested loops", "lines"
- Trigger Rules: If the user wants to evaluate code smells or style, assign "ruff" (generic linter). If they mention specific boundaries, map them to your native AST validators: "check_function_length" or "check_class_length".

4. PILLAR D: UNIT RUNNERS & CODE COVERAGE
- Keywords: "test", "pytest", "run tests", "coverage", "test percentage"
- Trigger Rules: If the user mentions testing, assign the strategy "pytest". If they explicitly mention tracking "coverage" or "percentage", you MUST include "pytest" and toggle your internal coverage flag fields.

5. GENERIC AST HOOK COGNITIVE SCAVENGERS
- Keywords: "transaction atomic", "db wrapper", "docstrings", "documentation comments"
- Trigger Rules: Map these precisely to "check_transaction_atomic" or "check_docstrings" using your parameters interface setup mapping block.


### ENVIRONMENT VARIABLE INJECTION & CONTEXT BOUNDARY RULES

Environment-key operations have one target scope per task: workspace OR repo. Never both.
Workspace target: when the user names a workspace, set workspace_name to that name and repositories = []. Do not ask for repositories. The workspace itself is the target.
Repository target: when the user names one or more repositories, set workspace_name = null and put the repo names in repositories. Do not ask for a workspace.
The schema fields are optional scope fields; their presence does not make the other scope required. Never invent or infer a workspace/repository that the user did not specify.
If the user gives no scope, stop and ask whether the operation should target a workspace or repository.
For deletion, use separate RepoEnvKeyDeletionTask objects when the prompt contains different scopes. A workspace deletion must have repositories = []; a repo deletion must have workspace_name = null.
If repository IDs are required internally, resolve them from the repository names; never ask the user for database IDs.
    
### CONTEXT EVOLUTION & HISTORY OVERHAUL PROTOCOL:
- For standard casual chats or technical inquiries, leave 'evict_prior_history' as False and 'condensed_history_summary' as None.
- The exact moment the user issues an operational execution command (e.g., "Run the first 2"), map the references to 'active_rules', set 'evict_prior_history' to True, and use your intelligence to populate 'condensed_history_summary'.
- Inside 'condensed_history_summary', extract ONLY the critical contextual baseline established prior to execution, combined with a record of the tools just launched. Strip all fluff, greetings, or basic question loops. 

Example Summary Output:
"User verified platform capabilities for pytest/bandit. Consolidated active workflow initiated for repo-b running strategy models: bandit, pytest."

### MANDATORY BRANCH CONFIGURATION & EXPLICIT CLARIFICATION RULES:
1. When a user requests any tool execution run or rule assignment, you must find explicit branch context names in the text (e.g., 'main', 'master', 'test', 'new').
2. **NEVER ASSUME OR FACTORY-DEFAULT A BRANCH NAME.** You are completely forbidden from guessing, inventing, or automatically filling a default branch name (like 'master' or 'main') if it was not explicitly provided by the user.
3. If the user provides a list of branches and repositories, use logical sequential mapping (e.g., Repository 1 -> Branch 1, Repository 2 -> Branch 2).
4. Identify repository targets from the CURRENT execution request. NEVER automatically reuse the repository list from a previous execution.
5. If the user says "same thing", "same checks", or similar, reuse the PREVIOUS CHECK STRATEGIES only. Do NOT automatically reuse the previous repository scope.
6. **CRITICAL INTENT OVERRIDE GATE FOR CLARIFICATIONS:**
   - If the user requests an execution but provides NO branch keyword, or if the branch layout mapping is ambiguous, you MUST IMMEDIATELY HALT ALL PIPELINE EXECUTION.
   - You MUST overwrite the 'intents' list to contain strictly ONE single token: ["technical_query"]. You are completely FORBIDDEN from including "run_static_analysis", "create_repo_env", "delete_workspace", or "delete_repo_env" in the intents array when a branch clarification is happening.
   - Set 'ui_layout_route' to "CHAT".
   - Keep 'active_rules', 'workspaces_to_delete', 'env_keys_to_create', and 'env_keys_to_delete' completely empty [].
   - Use your 'chat_response' to cleanly ask the user to explicitly specify which branch you should execute the tools against (e.g., "I see you want to run analysis on 'Taskmaster'. Could you please specify which branch I should run these checks on?").

   
### INTENT PARSING AND MAPPING BOUNDARY RULES
- "create_workspace": Select this if the user wants to group fresh repositories under a brand new workspace container. Sanitized loose repository names (e.g., "repo a", "z") into standard layouts (e.g., "repo-a").
- "delete_workspace": Select this intent if the user commands you to drop, remove, clear, or delete a workspace container. Populate the 'workspaces_to_delete' object array using name parameters from text and temporary integer placeholders for required numerical fields.
- "create_repo_env": Select this intent if the user wants to append, create, or bulk-inject environment variable keys across workspace contexts or repository boundaries.
- "delete_repo_env": Select this intent if the user requests the removal, dropping, stripping, or deletion of keys from environment lists.
- "run_static_analysis": Select this intent ONLY if the user uses explicit, active commands ordering you to kick off, launch, run, or execute a test block run immediately (e.g., "Run pytest now", "Execute security audit"). You MUST populate the active_rules array mapping strategies to their target repositories.
- "technical_query": Select this intent if the user is asking a general question about options, capabilities, configurations, or checking what is possible without explicitly ordering a live execution run right now (e.g., "Can you run tests?", "How do I check types?"). When this intent is selected, the active_rules list MUST remain empty.

"""




@shared_task(
    bind=True,
    autoretry_for= UNIVERSAL_NETWORK_ERRORS,
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,        
    retry_backoff_max=30
)
def process_agentic_chat_turn_task(self, channel_name, user_id, username, token, session_id, prompt_text, repos, provider, model_name, api_key):
    channel_layer = get_channel_layer()
    
    # -------------------------------------------------------------------------
    # PHASE 1: FAST DATABASE READ (Get past records instantly)
    # -------------------------------------------------------------------------
    if not prompt_text:
        return
    
    with transaction.atomic():
        user = User.objects.get(pk=user_id)
        session, _ = ChatSession.objects.get_or_create(pk=session_id, defaults={"user": user})
        past_messages = list(session.messages.all().order_by('created_at')[:15])
        past_messages.reverse()

    history_messages = []
    history_payload = []
    for msg in past_messages:
        if msg.role == "user":
            history_messages.append(
                HumanMessage(content=msg.content)
            )
            history_payload.append({"role": "user", "content": msg.content})
        elif msg.role == "ai":
            history_messages.append(
                AIMessage(content=msg.content)
            )
            history_payload.append({"role": "ai", "content": msg.content})


    # Assemble your structural Prompt Template using ONE clean system message entry
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_instruction_text),
        # 🚀 THE NATIVE FIX: Pass history as an explicit, independent structural message entry block!
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")                                        
    ])

    # Dynamic model vendor factory setup based on your Zustand selection state
    if provider == "openai":
        llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)
    else:
        key = settings.GEMINI_API_KEY
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=key)

    # Bind the Pydantic schema class structure natively to the model runner engine
    structured_llm = llm.with_structured_output(OrchestratorAction)
    chain = prompt_template | structured_llm

    try:
        # -------------------------------------------------------------------------
        # PHASE 2: LONG NETWORK API CALL (Token Tracking Context - No DB Lock)
        # -------------------------------------------------------------------------
        with get_openai_callback() as cb:
            result = cast(OrchestratorAction , chain.invoke({
                "history": history_messages, 
                "input": prompt_text.strip()
            }))
            
            prompt_tokens = cb.prompt_tokens
            completion_tokens = cb.completion_tokens
            total_cost = cb.total_cost

            print("🗂️ FULL STRUCTURAL DATA RECOVERED:")
            print(result.active_rules)
            # print(json.dumps(result.model_dump(), indent=2)) 
            print(prompt_tokens, "chim", completion_tokens, "uche", total_cost)
            print(result)
            print("============================================================\n")


        # -------------------------------------------------------------------------
        # PHASE 3: CONTEXT CONVERSATION OVERHAUL & BASELINE SEEDING
        # -------------------------------------------------------------------------
        ui_layout_route = result.ui_layout_route
        chat_response = result.chat_response

        with transaction.atomic():
            if result.evict_prior_history:
                # 1. 🧹 THE OVERHAUL: Instantly wipe out all past messages for this session
                session.messages.all().delete()                
                # 2. Save the current user text prompt as the first record of the new era
                ChatMessage.objects.create(session=session, role="user", content=prompt_text)
                
                # Saving the LLM's own high-utility condensed text summary
                # This becomes the single baseline row memory anchor for the next message turn!
                summary_marker = f"""
                    [ACTIVE SYSTEM CONTEXT BASELINE]:
                    The following infrastructure states were successfully verified and created by you in previous turns:
                    {result.condensed_history_summary}
                """
                ChatMessage.objects.create(session=session, role="ai", content=summary_marker)
            else:
                # 📥 STANDARD WORKING MEMORY: Save strings sequentially during casual Q&A phases
                ChatMessage.objects.create(session=session, role="user", content=prompt_text)
                ChatMessage.objects.create(session=session, role="ai", content=result.chat_response)



        # -------------------------------------------------------------------------
        # 🚀 BRIDGE PLUG: INTERCEPT THE DESIGN INTENTS & TRIGGER YOUR CORE PIPELINE
        # -------------------------------------------------------------------------
        # We look up the GitHub owner/username from the active authenticated user profile context
        repo_owner = user.username 

        print(result.intents, "and", result.active_rules)
        details_cache_key = f"user:repos:{user_id}"
        cached_details = cache.get(details_cache_key)
        # print(token,"cached_repos", cached_details, "bro")
        # Check if data exists and is the correct format (list or dict of repos)
        if cached_details is not None:
            # Process your cached_repos directly here
            cached_repos = cached_details.get("repo_names", {})
            print(f"⚡ [CACHE HIT] Celery successfully loaded repositories for key: {cached_repos}")
        else:
            print(f"⚠️ Cache Miss or Invalid Type for key: {details_cache_key}. Falling back to standard processing.")
         
            repos_url = f"https://api.github.com/users/{username}/repos"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Django-Application-Gateway" # GitHub drops headers lacking identifiers
            }

            try:
                github_res = requests.get(repos_url, headers=headers, params={"per_page": 100, "sort": "updated"}, timeout=5.0)
                print(f"📊 [GITHUB API] External status responded: {github_res.status_code}")
                repositories_data = github_res.json() if github_res.status_code == 200 else []
                github_res_status = github_res.status_code
                print("github repositories_data", repositories_data)
                cleaned_repos = []
                # for easy access in tasks.py
                repo_names = []

                for r in repositories_data:
                    # 1. Defensive type check
                    if not isinstance(r, dict):
                        continue
                        
                    name = r.get("name")
                    
                    # 2. Append to full structured list
                    cleaned_repos.append({
                        "id": r.get("id"),
                        "name": name,
                        "full_name": r.get("full_name"),
                        "default_branch": r.get('default_branch') 
                    })
                    
                    # 3. Simultaneously append to the flat name list
                    if name:
                        repo_names.append(name)


                # Commit cleaned structures to Redis with a highly scalable 1-hour lifecycle TTL (3600s)
                if github_res_status == 200:
                    cached_details["repositories"] = cleaned_repos
                    cache.set(details_cache_key, cached_details, timeout=28800)

            except requests.RequestException as e:
                print(f"Error occurred while fetching repositories: {e}")
                async_to_sync(channel_layer.group_send)(
                    channel_name,
                    {
                        "type": "chat_message",
                        "payload": {"type": "error", "message": f"❌ [GITHUB API] Error occurred while fetching repositories: {e}"}
                    }
                )
                
                return

        
        # 2. BuildIing concurrent execution canvas signature list array
        intent_signatures = []
        cached_repositories = cached_details.get("repositories", [])



        if "run_static_analysis" in result.intents:

            installed_github_code = (
                UserProfileModel.objects
                .get(user=user)
                .installation_id
            )

            cached_pairs = [
                (
                    repo.get("name", "").lower(),
                    repo
                )
                for repo in cached_repositories
                if isinstance(repo, dict)
            ]

            for rule in result.active_rules:

                repo_name = (
                    rule.repo_name
                    .lower()
                    .replace(" ", "-")
                    .strip()
                )

                matched_repo = next(
                    (
                        repo
                        for low_name, repo in cached_pairs
                        if repo_name in low_name
                    ),
                    None,
                )

                if not matched_repo:
                    continue

                intent_signatures.append(

                    run_agentic_pipeline.s(

                        channel_name=channel_name,

                        repo_owner=repo_owner,

                        repo_name=repo_name,

                        default_branch=matched_repo.get(
                            "default_branch",
                            "main"
                        ),

                        repo_data=cached_repositories,


                        target_branch=(
                            rule.target_branch
                            or matched_repo.get(
                                "default_branch",
                                "main"
                            )
                        ),

                        installation_id=installed_github_code,

                        user_requested_rules=rule.strategies,

                    )
                )


        if "create_workspace" in result.intents:
            # 🚀 PASS THE CACHED REPO LIST DIRECTLY AS A PARAMETER HERE TOO!
            
            
            # 2. 🚀 THE TYPE-SAFE FIX: No square brackets used! 
            # You pass the task path name string and your parameters directly inside signature()
            result_dict = result.model_dump()
            serializable_workspaces = result_dict.get('workspaces_to_create', [])
            ui_layout = result_dict.get('ui_layout', [])
            cached_repositories = cached_details.get("repositories", [])
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_workspace_creation_task",
                    args=(serializable_workspaces, channel_name,user_id, cached_repositories, ui_layout) # 📥 Pass your variables as an ordered tuple
                )
            )

        
        if "delete_workspace" in result.intents:            
            # 2. 🚀 THE TYPE-SAFE FIX: No square brackets used! 
            # You pass the task path name string and your parameters directly inside signature()
            result_dict = result.model_dump()
            serializable_workspaces = result_dict.get('workspaces_to_delete', [])
            print("serializable_workspaces", serializable_workspaces)
            ui_layout = result_dict.get('ui_layout', [])
            cached_repositories = cached_details.get("repositories", [])
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_workspace_deletion_task",
                    args=(serializable_workspaces, channel_name,user_id, cached_repositories, ui_layout)
                )
            )


        if "create_repo_env" in result.intents:
            
            # 2. 🚀 THE TYPE-SAFE FIX: No square brackets used! 
            # You pass the task path name string and your parameters directly inside signature()
            result_dict = result.model_dump()
            env_key_requests = result_dict.get('env_keys_to_create', [])
            ui_layout = result_dict.get('ui_layout', [])
            cached_repositories = cached_details.get("repositories", [])
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_env_key_creation_task",
                    args=(env_key_requests, channel_name,user_id, ui_layout, cached_repositories) 
                )
            )

       
        if "delete_repo_env" in result.intents:
            
            # passing the task path name string and  parameters directly inside signature()
            result_dict = result.model_dump()
            env_key_requests = result_dict.get('env_keys_to_delete', [])
            ui_layout = result_dict.get('ui_layout', [])
            cached_repositories = cached_details.get("repositories", [])
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_env_key_deletion_task",
                    args=(env_key_requests, channel_name,user_id, ui_layout, cached_repositories) # 📥 Pass your variables as an ordered tuple
                )
            )



        # Fire all intent tasks concurrently and run follow-up only after they're done.
        if intent_signatures:
            print(f"intent-error-{error_data}")
            callback_signature = signature(
                "agents.tasks.agentic_chat_follow_up",
                kwargs={
                    "provider": provider,
                    "model_name": model_name,
                    "api_key": api_key,
                    "channel_name": channel_name,
                    "session_id": session_id,
                    "history_payload": history_payload
                },
            )
            workflow_canvas = group(intent_signatures) | callback_signature
            workflow_canvas.apply_async()

        
        print("coat", "swaaaaa")

        # The follow-up task will be dispatched as a chord callback and therefore
        # will execute after all intent tasks complete.
        
        # 🚀 FIXED: Swapped from .send to .group_send to connect to group_user_room static strings safely!
        async_to_sync(channel_layer.group_send)(
            channel_name, # Targets the static room name string
            {
                "type": "chat_message",
                "payload": {
                    "type": "orchestration_result",
                    "raw_output": {"ui_layout_route":ui_layout_route, "chat_response":chat_response},
                    "usage": {
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "cost": total_cost
                    }
                }
            }
        )

    except Exception as e:
        print("=" * 80)
        print("EXCEPTION TYPE:", type(e))
        print("EXCEPTION:", repr(e))
        traceback.print_exc()
        print("=" * 80)
        
        # 🚀 FIXED: Swapped from .send to .group_send for fallback alerts too!
        async_to_sync(channel_layer.group_send)(
            channel_name,
            {
                "type": "chat_message",
                "payload": {"type": "error", "message": str(e)}
            }
        )




@shared_task
def async_handle_workspace_creation_task(workspaces,channel_name, user_id, parent_repo_list, ui_layout):
    """
    Runs in parallel with zero cache lag hooks.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    if not workspaces:
        return
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
            channel_name, # Targets the static room name string
            {
                "type": "chat_message",
                "payload": {
                    "type": "orchestration_result",
                    "raw_output": {
                        "ui_layout_route":ui_layout, 
                        "chat_response":"Processing Workspace creation task",
                    }
                }
            }
        )

    # Storing the whole raw repo dict tied to its lowercase matching key
    cached_pairs = [(repo.get('name', '').lower(), repo) for repo in parent_repo_list if isinstance(repo, dict)]

    
    workspace_list = workspaces if isinstance(workspaces, list) else [workspaces]

    if len(workspace_list)>0:
        for ws in workspace_list:
            ws_name = ws.get("new_workspace_name")
            raw_repos = ws.get("repositories", [])
            
            repos_found = []
            repos_not_found = []

            for raw_repo in raw_repos:
                user_input = raw_repo.lower().replace(" ", "-").strip()
                
                # Find the full repository dictionary payload match from Redis cache
                matched_repo_dict = next((repo for low_name, repo in cached_pairs if user_input in low_name), None)
                
                if matched_repo_dict:
                    # 2. 🚀 FIX: Structure the exact schema fields your Serializer expects!
                    # Adjust these keys ('repo_id', 'repo_name', etc.) to match your actual serializer fields
                    full_name = matched_repo_dict.get("full_name", "")
                    repo_owner = full_name.split("/")[0] if "/" in full_name else user.username

                    serializer_ready_data = {
                        "repo_id": matched_repo_dict.get("id"),
                        "repo_name": matched_repo_dict.get("name"),
                        "repo_full_name": full_name,
                        "repo_owner": repo_owner
                    }
                    repos_found.append(serializer_ready_data)
                else:
                    repos_not_found.append(raw_repo)
                    error_data["repo_resolution_for_workspace_creation_not_found"] = {
                        "status": "error",
                        "message": f"Repository '{user_input}' not found."
                    }

            # 3. Safe validation pass execution
            if len(repos_found) > 0:
                workspace_and_repo_result = create_workspace_with_repos(user, ws_name, repos_found)
                error_data.update(workspace_and_repo_result)
                return error_data
            else:
                error_data.update({"No_repos_found":f"No repos found for workspace: {ws_name}"})
                
    return "No workspace list"




@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,         
    retry_backoff_max=15        
)
def async_handle_workspace_deletion_task(self, workspaces_to_delete, channel_name, user_id, cached_repositories, ui_layout):
    """
    Executes bulk workspace deletions and unlinking asynchronously.
    Fires status updates back to the browser via WebSockets.
    """
    print("delete_workspace", workspaces_to_delete, "iwee")
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User not found"

    if not workspaces_to_delete:
        return "No workspaces provided for deletion"

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        channel_name,
        {
            "type": "chat_message",
            "payload": {
                "type": "orchestration_result",
                "raw_output": {
                    "ui_layout_route": ui_layout,
                    "chat_response": "Processing Workspace deletion Request",
                },
            }
        }
    )
    workspace_id = None
    workspace_not_found = []
    # Ensure standard list structure handling even if a singular dictionary lands
    deletion_list = workspaces_to_delete if isinstance(workspaces_to_delete, list) else [workspaces_to_delete]
    print(f"daaluuu-{deletion_list}")
    
    deletion_summaries = []
    deletion_error_summaries = []

    if len(deletion_list)>0:
        for ws_task in deletion_list:
            # Support lookups via 'workspace_id' integer keys, falling back to name parameters if required
            # Adjust these parameter keys to match your exact Pydantic schema naming structure!
            workspace_name = ws_task.get("workspace_name")
            print(f"oh chim- {workspace_name}")

            # Fallback tracking resolution step: If the LLM only gave a string name, look it up in the database
            if workspace_name:
                db_workspace = Workspace.objects.filter(name=workspace_name.strip(), owner=user).first()
                if db_workspace:
                    workspace_id = db_workspace.pk
                else:
                    workspace_not_found.append(workspace_name)
                print("gang",db_workspace, "old")


            if not workspace_id:
                print(f"⚠️ Deletion Skipped: Could not resolve a valid target ID for context: {workspace_name}")
                continue
            print("workspace_id", workspace_id)
            try:
                # 1. Fire your decoupled service processing transaction logic block
                execution_result = delete_workspace_with_repos(
                    user=user,
                    workspace_id=int(workspace_id)
                )
                if workspace_not_found:
                    execution_result.update({"workspace_not_found":execution_result})
                deletion_summaries.append(execution_result)

            except Exception as deletion_error:
                print(f"🚨 Failed processing deletion thread loop for ID {workspace_id}: {str(deletion_error)}")
                deletion_error_summaries.append(f"Failed processing deletion thread loop for ID {workspace_id}: {str(deletion_error)}")
                continue

        if len(deletion_summaries)>0:       
            return deletion_summaries
        # if error
        if deletion_error_summaries:       
            return deletion_error_summaries
        
    else:
        return "No deletion list for backend"




@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,         # Exponential backoff (1s, 2s, 4s, 8s...)
    retry_backoff_max=15        # Max wait limit per retry
)
def async_handle_env_key_creation_task(self, env_key_requests, channel_name, user_id, ui_layout, parent_repo_list):
    """
    Asynchronously processes environment key mapping and repository linking.
    Supports polymorphic execution: Workspace-wide scope or Repository-explicit scope.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User context verification failure"


    if not env_key_requests:
        return "No configuration data provided"

    channel_layer = get_channel_layer()
        # 🚀 IMMEDIATE BROADCAST: Push the success summary metrics right out to the client browser
    async_to_sync(channel_layer.group_send)(
        channel_name,
        {
            "type": "chat_message",
            "payload": {
                "type": "orchestration_result",
                "raw_output": {
                    "ui_layout_route": ui_layout,
                    "chat_response": "Processing Repo creation request",
                },
            }
        }
    )

    key_creation_summaries = []
    key_creation_error_summaries = []
    
    # Ensure list type checking compliance even if a single dict object lands from the LLM
    requests_list = env_key_requests if isinstance(env_key_requests, list) else [env_key_requests]

    # Map the full repository array cache list natively for safe matching bounds
    cached_map = [(repo.get('name', '').lower().strip(), repo) for repo in parent_repo_list if isinstance(repo, dict)]
    print("env_key_requests", requests_list)

    if len(requests_list)>0:
        for req in requests_list:
            # 🌟 INITIALIZE VARIABLES INSIDE THE LOOP BODY PER REQUEST CONTEXT
            workspace_name = req.get("workspace_name")
            raw_key_names = req.get("key_names", [])
            raw_target_repos = req.get("repositories", [])
            
            selected_repo_ids = []
            repos_not_found = []
            print("lisa",  raw_target_repos)

            # 1. 🔍 Try to match explicitly passed repositories if they exist in the payload
                    # 1. 🔍 Try to match explicitly passed repositories if they exist in the payload
            if raw_target_repos:
                for raw_item in raw_target_repos:
                    # 🌟 FIX A: Extract the repository name string safely depending on data type
                    if isinstance(raw_item, dict):
                        repo_name_str = raw_item.get("repo_name", "")
                    else:
                        repo_name_str = str(raw_item)

                    user_input = repo_name_str.lower().replace(" ", "-").strip()
                    
                    # Execute the safe tuple-list match wrapper clean
                    matched_repo_dict = next((repo for low_name, repo in cached_map if user_input in low_name), None)
                    print("matched_repo_dict", matched_repo_dict)
                    
                    if matched_repo_dict:
                        matched_id = matched_repo_dict.get("id")
                        if matched_id:
                            selected_repo_ids.append(matched_id)
                    else:
                        # 🌟 FIX B: Fallback directly to the incoming layout metadata payload 
                        # if the cache does not have this repository loaded yet
                        if isinstance(raw_item, dict):
                            incoming_id = raw_item.get("repo_id")
                            # Only append if it's a real database primary key (not placeholder 0)
                            if incoming_id and incoming_id != 0:
                                selected_repo_ids.append(incoming_id)
                                continue
                        
                        repos_not_found.append(user_input)
                        error_data["repo_resolution_for_key_creation_not_found"] = {
                            "status": "error",
                            "message": f"Repository '{user_input}' not found."
                        }

                # If user targeted specific repos but none could be verified, halt this specific request
                if not selected_repo_ids:
                    print(f"⚠️ Env Key Warning: Explicit repositories targeted but none verified for: {raw_target_repos}")
                    continue


            # 2. ⚡ MOVE TRY BLOCK INSIDE THE LOOP CONTEXT
            try:
                print("qqqqqqqqqqqqqqqq - Target scope verified online.")
                
                # Invoke your business service function natively inside the loop
                service_result = create_repo_env_keys_service(
                    user=user,
                    repositories_data=parent_repo_list, 
                    key_names=raw_key_names,
                    workspace_name=workspace_name,
                    selected_repo_ids=selected_repo_ids  # Passes empty list cleanly if workspace scope is targeted
                )

                key_creation_summaries.append(service_result)

                
            except Exception as service_error:
                key_creation_error_summaries.append(service_error)
                print(f"🚨 Background worker environmental key processing failure: {str(service_error)}")
                continue

        if key_creation_error_summaries:
            error_data.update({
                "status": "error",
                "message": f"Background worker environmental key creation failure: {str(service_error)}."
            })   
            return error_data
        
        if key_creation_summaries:
            error_data.update({"key_creation_summaries":key_creation_summaries })   
            return error_data
    else:
        return "No Request list for backend" 



@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,         
    retry_backoff_max=15        
)
def async_handle_env_key_deletion_task(self, env_key_requests, channel_name, user_id, ui_layout, parent_repo_list):
    """
    Asynchronously processes environment key deletion parameters.
    Fires removal logs directly down the user's secure room WebSocket pipe.
    """
    print("patty1111")
    try:
        print("patty222")
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return "User context verification failure"

    if not env_key_requests:
        print("patty3333", env_key_requests)
        return "No configuration data provided for key deletion"
    
    print("patty")

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        channel_name,
        {
            "type": "chat_message",
            "payload": {
                "type": "orchestration_result",
                "raw_output": {
                    "ui_layout_route": ui_layout,
                    "chat_response": "Processing Env Key deletion task" ,
                },
            }
        }
    )
    key_deletion_summaries = []
    key_deletion_error_summaries = []


    requests_list = env_key_requests if isinstance(env_key_requests, list) else [env_key_requests]

    # Map the full repository array cache list natively for safe matching bounds
    cached_map = [(repo.get('name', '').lower().strip(), repo) for repo in parent_repo_list if isinstance(repo, dict)]

    if len(requests_list)>0:
        for req in requests_list:
            raw_key_names = req.get("key_names", [])
            raw_target_repos = req.get("repositories", []) or req.get("repo_names", [])
            delete_which= req.get("delete_which", None)
            workspace_name= req.get("workspace_name", None)
            selected_repo_ids = []
            selected_repo_names = set()

            print("ev-requests_list", requests_list,"rrr")

            # Match loose string inputs to your parent cached array list items to gather specific IDs
            for raw_name in raw_target_repos:
                user_input = str(raw_name).lower().replace(" ", "-").strip()
                
                matched_repo_dict = next((repo for low_name, repo in cached_map if user_input in low_name), None)

                print("matched_repo_dict", matched_repo_dict, "env-raw_name", raw_name)
                if matched_repo_dict:
                    matched_id = matched_repo_dict.get("id")
                    if matched_id:
                        selected_repo_ids.append(matched_id)
                        selected_repo_names.add(matched_repo_dict.get("name"))
            print("diamond",workspace_name,"raw_key_names", raw_key_names, "masked", selected_repo_ids)
            if not selected_repo_ids and not raw_key_names and not workspace_name:
                print(f"⚠️ Env Key Deletion Warning: Missing parameter targets inside request: {req}")
                continue

            try:
                # Execute the core transaction service function natively inside the background task loop
                service_result = delete_repo_env_keys_service(
                    user=user,
                    key_names=raw_key_names,
                    delete_which=delete_which,
                    workspace_name = workspace_name,
                    selected_repo_ids=selected_repo_ids,
                    selected_repo_names= selected_repo_names
                )

                print("service_result", service_result)
                key_deletion_summaries.append(service_result)



            except Exception as service_error:
                key_deletion_error_summaries.append(service_error)
                print(f"🚨 Background worker environmental key deletion failure: {str(service_error)}")
                continue

        if key_deletion_error_summaries:
            error_data.update({
                "status": "error",
                "message": f"Background worker environmental key creation failure: {str(service_error)}."
            })   
            return error_data
        
        if key_deletion_summaries:
            error_data.update({"key_deletion_summaries":key_deletion_summaries })   
            return error_data
    else:
        return "No Request list for backend" 




@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_kwargs={'max_retries': 5},
    retry_backoff=True,         
    retry_backoff_max=15        
)
def run_agentic_pipeline(self,channel_name,  repo_owner, repo_name,default_branch, repo_data,target_branch,installation_id, user_requested_rules):
    """
    Asynchronous platform dispatcher.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
            channel_name,
            {
                "type": "chat_message",
                "payload": {
                    "type": "orchestration_result",
                    "raw_output": {
                        "ui_layout_route": "CHAT",
                        "chat_response": "Started processing on github" ,
                    },
                }
            }
        )
    # =========================================================================
    # ✅ STEP 0: GENERATE DYNAMIC 1-HOUR TOKEN VIA PRIVATE KEY
    # =========================================================================
    try:
        # Trade installation_id + private key file for an active execution token
        git_token = get_installation_access_token(installation_id)
    except Exception as e:
        print(f"CRITICAL: Token generation failed: {str(e)}")
        return {"status": "error", "message": "Authentication token exchange failure"}

    # =========================================================================
    # STEP 1: SCRIPT STITCHING ENGINE (Your existing logic)
    # =========================================================================
    resolved_repo_name = ensure_orchestrator_yaml_is_online(repo_owner, repo_name, target_branch, git_token, repo_data, channel_name)
    print("as-what_nah", resolved_repo_name)
    if resolved_repo_name.get("status") != "success":
        print(f"CRITICAL: Orchestrator YAML validation failed - {resolved_repo_name.get('message')}")
        return resolved_repo_name

    print("")
    print("amapiano",default_branch,{"default_branch": user_requested_rules})
    base_classes_text = inspect.getsource(rule_classes)
    
    # Strip any local manual __main__ loop if it exists in your file text
    if 'if __name__ == "__main__":' in base_classes_text:
        base_classes_text = base_classes_text.split('if __name__ == "__main__":')[0].strip()

    visitor_instances_lines = []

    strategies_dict = {}
    if isinstance(user_requested_rules, dict):
        strategies_dict = user_requested_rules
    elif isinstance(user_requested_rules, list):
        # Maps old format: [{"rule_key": "x", "params": {...}}] into flat dict keys
        for item in user_requested_rules:
            if isinstance(item, dict) and "rule_key" in item:
                strategies_dict[item["rule_key"]] = item.get("params", {})
    
    
    for rule_key, rule_payload in strategies_dict.items():
        # Only process tools registered in our AST engine toolkit
        if rule_key in AST_TOOL_REGISTRY:
            class_name = AST_TOOL_REGISTRY[rule_key].__name__
            
            # DEFENSIVE ACCIDENT PROTECTION: Ensure rule_payload is a dictionary
            payload_data = rule_payload if isinstance(rule_payload, dict) else {}
            
            # Preserve rule-specific options (for example ``required_auth``),
            # while guaranteeing the common nested dictionaries expected by the
            # constraint visitors.
            sanitised_payload = dict(payload_data)
            sanitised_payload.setdefault("target", {})
            sanitised_payload.setdefault("constraints", {})
            
            # Stitch the class initialization line safely using valid layout arguments
            line = f"            {class_name}({json.dumps(sanitised_payload)}),"
            visitor_instances_lines.append(line)
            
    visitors_code_block = "\n".join(visitor_instances_lines)

    raw_template = f"""
    if __name__ == "__main__":
        import os
        import json
        
        visitors = [
{visitors_code_block}
        ]
        print("VISITORS CREATED:", visitors)
        all_findings = []
        
        for root, dirs, files in os.walk("."):
            if "venv" in root or ".git" in root or "migrations" in root:
                continue
            for file in files:
                if file.endswith(".py") and file != "odozi_runner.py":
                    full_path = os.path.join(root, file)
                    print("ANALYZING:", full_path)
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            code = f.read()
                        
                        # The generated checks are ``ast.NodeVisitor`` classes.
                        # They expose ``visit`` and a ``findings`` list; they do
                        # not implement an ``analyze_file`` method.
                        tree = ast.parse(code, filename=full_path)

                        for visitor in visitors:
                            try:
                                # A visitor instance is reused for every file,
                                # so reset its findings before visiting this AST.
                                visitor.findings = []
                                visitor.visit(tree)
                                findings = visitor.findings

                                for finding in findings:
                                    if isinstance(finding, dict):
                                        finding.setdefault("file", full_path)

                                print(
                                    visitor.__class__.__name__,
                                    "found",
                                    len(findings),
                                    "issues in",
                                    full_path
                                )
                                all_findings.extend(findings)
                            except Exception as visitor_error:
                                # A faulty rule must not stop other visitors
                                # from analysing the current file.
                                print(
                                    f"ERROR running {{visitor.__class__.__name__}} "
                                    f"on {{full_path}}: {{visitor_error}}"
                                )
                    except Exception as e:
                        print(
                            f"ERROR processing {{full_path}}: {{e}}"
                        )
                                            
        print(json.dumps({{"tool": "odozi_visitors", "findings": all_findings}}))
    """

    execution_loop_template = textwrap.dedent(raw_template)
    final_payload_string = base_classes_text.strip() + "\n\n" + execution_loop_template.strip()
    encoded_script = base64.b64encode(
        final_payload_string.encode()
    ).decode()
    
    # =========================================================================
    # STEP 2: DISPATCH TO LIVE GITHUB API (Uncomment when ready to go live)
    # =========================================================================
    async_to_sync(channel_layer.group_send)(
                channel_name,
                {
                    "type": "chat_message",
                    "payload": {
                        "type": "orchestration_result",
                        "raw_output": {
                            "ui_layout_route": "CHAT",
                            "chat_response": "Dispatching to Github" ,
                        },
                    }
                }
            )
    print("user_requested_rules", user_requested_rules)
     # 1. Start a clean flat list for your GitHub Actions YAML checkboxes
    yaml_tools_list = []

    # 2. Iterate through whatever keys the user/LLM requested
    for rule_key in strategies_dict.keys():
        # A. If it's an internal AST check, append 'odozi_visitors' to light up Job 4
        if rule_key in AST_TOOL_REGISTRY:
            if "odozi_visitors" not in yaml_tools_list:
                yaml_tools_list.append("odozi_visitors")
        else:
            # B. If it's a native runner rule (like 'bandit', 'pytest', or 'ruff'), 
            # pass it straight through to light up its individual Job block
            yaml_tools_list.append(rule_key)


    
    # 2. Fetch only the variable names registered for THIS specific repository
    repo_merge = f'{repo_owner}/{repo_name}'
    # repo_instance = GitHubRepository.objects.get(repo_name=repo_merge)
    registered_keys = RepoEnvKey.objects.filter(
         repo__repo_name=repo_merge
    ).values_list('key_name', flat=True)
    
    # Example output string: '["DJANO_SECRET_KEY"]'
    env_keys_payload = json.dumps(list(registered_keys)) if registered_keys else "[]"
    matched_repo_name = resolved_repo_name.get('repo')
    print(f"estavao-{matched_repo_name}")
    url = (
        f"https://api.github.com/repos/"
        f"{repo_owner}/{matched_repo_name}/actions/workflows/"
        f"orchestrator.yaml/dispatches"
    )    
    headers = {
        "Authorization": f"Bearer {git_token}", 
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    api_payload = {
        "ref":  target_branch,  
        "inputs": {
            "tools_list": json.dumps(yaml_tools_list),
            "custom_script_payload": encoded_script,
            "env_keys_list": env_keys_payload
        }
    }
    
    print(matched_repo_name, "DEBUG: Dispatching to GitHub API with payload:", url)
    print("=================== PROOF OF PAYLOAD FORMATS ===================")
    print(f"1. RAW user_requested_rules (From LLM): {user_requested_rules}")
    print(f"2. STRATEGIES DICT (Extracted): {strategies_dict}")
    print(f"3. WHAT DISPATCH RECEIVED (tools_list): {json.dumps(user_requested_rules)}")
    print("================================================================")

    feedback_r = requests.post(url, json=api_payload, headers=headers)
    if feedback_r.status_code == 204:
        print("🎉 SUCCESS! GitHub successfully accepted the workflow dispatch request.")
        resolved_repo_name.update({
            "status": "success",
            "tasks":"Deploy to Github",
            "repo": matched_repo_name if matched_repo_name else "",
            "message": "Repo and branch resolved. Pipeline launched on github successfully."
        })
        return resolved_repo_name
        
    else:
        print(f"❌ GITHUB ERROR [{feedback_r.status_code}]: {feedback_r.text}")
        resolved_repo_name.update({
            "status": "validation_error",
            "tasks":"Deploy to Github",
            "repo":matched_repo_name if matched_repo_name else "",
            "message": feedback_r.text
        })
        return resolved_repo_name



@shared_task(
    bind=True,
    autoretry_for= UNIVERSAL_NETWORK_ERRORS,
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=30
)
def agentic_chat_follow_up(
    self,
    task_results: List[Any] = None,
    provider: str = "",
    model_name: str = "",
    api_key: str = "",
    channel_name: str = "",
    session_id: int = None,
    history_payload: List[Dict[str, str]] = None,
):
    # -------------------------------------------------------------------------
    # LIGHTWEIGHT SYSTEM INSTRUCTION
    # -------------------------------------------------------------------------
    short_followup_instruction = """
    You are the Error Resolution Core for Project Odozi, an autonomous agentic CI/CD gateway.

    Your task is to translate backend task results into a clear, concise,
    user-friendly response.

    ### RULES

    1. NEVER expose stack traces, IDs or internal backend implementation.
    2. Summarize successful operations.
    3. Explain failures in plain English.
    4. If clarification is required, politely ask for it.
    5. ALWAYS keep:
       - active_rules=[]
       - workspaces_to_create=[]
       - workspaces_to_delete=[]
       - env_keys_to_create=[]
       - env_keys_to_delete=[]
    6. ALWAYS set:
       ui_layout_route="FINISHED"
       intents=["technical_query"]
    """

    print("task_results:", task_results)

    # -------------------------------------------------------------------------
    # Prompt Template
    # -------------------------------------------------------------------------
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", short_followup_instruction),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])

    # -------------------------------------------------------------------------
    # LLM Factory
    # -------------------------------------------------------------------------
    if provider == "openai":
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=api_key
        )
    else:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )

    structured_llm = llm.with_structured_output(OrchestratorAction)
    chain = prompt_template | structured_llm

    # -------------------------------------------------------------------------
    # Restore Chat History
    # -------------------------------------------------------------------------
    history_messages: List[Any] = []

    if history_payload:
        for item in history_payload:
            if item.get("role") == "user":
                history_messages.append(
                    HumanMessage(content=item.get("content", ""))
                )
            else:
                history_messages.append(
                    AIMessage(content=item.get("content", ""))
                )

    # -------------------------------------------------------------------------
    # Build backend summary for the LLM
    # -------------------------------------------------------------------------
    backend_event_input = f"""
        The following backend tasks have completely finished executing.

        Task Results:

        {json.dumps(task_results, indent=2, default=str)}

        Instructions:

        • Summarize what completed successfully.
        • Explain any failures clearly.
        • Do not expose backend implementation details.
        • If the user needs to clarify something, ask politely.
    """

    print("backend_event_input", backend_event_input)

    try:

        with get_openai_callback() as cb:

            result = cast(
                OrchestratorAction,
                chain.invoke({
                    "history": history_messages,
                    "input": backend_event_input
                })
            )

            print("📊 Follow-up Result")
            print(result)

        # -----------------------------------------------------------------
        # Save conversation
        # -----------------------------------------------------------------
        with transaction.atomic():

            session = ChatSession.objects.get(pk=session_id)

            ChatMessage.objects.create(
                session=session,
                role="user",
                content=f"[Backend Task Results]: {json.dumps(task_results, default=str)}"
            )

            ChatMessage.objects.create(
                session=session,
                role="ai",
                content=result.chat_response
            )
        print(f"stunned-{channel_name}")
        async_to_sync(get_channel_layer().group_send)(
            channel_name,
            {
                "type": "chat_message",
                "payload": {
                    "type": "follow_up_result",
                    "raw_output": {
                        "ui_layout_route": result.ui_layout_route,
                        "chat_response": result.chat_response,
                        "task_results": task_results,
                    },
                },
            },
        )

        print("follow-up-done")
        return result.model_dump()

    except Exception as e:

        print("=" * 80)
        print("FOLLOW-UP FAILED")
        print(e)
        traceback.print_exc()
        print("=" * 80)

        return None


def handle_backend_error_followup( self,
    task_results: List[Any],
    error_data: Dict[str, Any],
    provider: str,
    model_name: str,
    api_key: str,
    channel_name: str,
    history_payload: List[Dict[str, str]] = None
    ):
    """
    Separate, lightweight function dedicated solely to error translation.
    """
    short_followup_instruction = """
        You are the Error Resolution Core for Project Odozi, an autonomous agentic CI/CD gateway. 
        Your sole task is to translate backend validation error dictionaries into helpful user feedback.

        ### 🛡️ CRITICAL SECURITY & OUTPUT BOUNDARIES:
        1. NEVER expose raw technical dictionary structures, IDs, or database stack trace strings to the user. Translate anomalies into clear, human-friendly guidance.
        2. ALWAYS keep 'active_rules', 'workspaces_to_delete', 'env_keys_to_create', and 'env_keys_to_delete' completely EMPTY [].
        3. ALWAYS set 'ui_layout_route' to "CHAT" and overwrite your 'intents' list to contain strictly one token: ["technical_query"].

        ### 📂 ERROR CONTEXT HANDLERS:
        - If 'repo_resolution' is present: State that you couldn't match the repository name cleanly. If multiple options are provided in the telemetry metrics, output them as a numbered list and ask the user to clarify which exact one they meant.
        - If 'workspace_resolution' is present: Politely notify the user that no active environment variables could be found associated with that specific workspace container path.

        Review the chat history to understand their intent, summarize what failed gracefully inside 'chat_response', and ask the user for clarification.
    """
     # Normalize the child task outputs into a consistent error list.
        # Child tasks may return dicts, strings, or simple status messages.
    
    def _normalize_child_result(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            return {"message": value}
        if isinstance(value, (list, tuple)):
            return {"task_result": list(value)}
        return {"task_result": str(value)}

    normalized_child_errors = []
    seen_errors = set()

    for child_result in task_results or []:
        normalized = _normalize_child_result(child_result)
        is_error = (
            normalized.get("status") == "error"
            or normalized.get("error") is not None
            or normalized.get("exception") is not None
            or normalized.get("message") is not None
        )
        if is_error:
            error_key = json.dumps(normalized, sort_keys=True, default=str)
            if error_key not in seen_errors:
                seen_errors.add(error_key)
                normalized_child_errors.append(normalized)

    error_data = error_data or {}
    error_data["child_errors"] = normalized_child_errors
    
    # 1. Fetch past chat logs so the model knows what the user originally requested
    session = ChatSession.objects.get(pk=session_id)
    past_messages = list(session.messages.all().order_by('created_at')[:10])
    
    # Assemble messages wrapper list array...
    history_messages = [] 
    # (Populate history_messages with HumanMessage/AIMessage objects from past_messages)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", short_followup_instruction),
        MessagesPlaceholder(variable_name="history"),
        ("human", "SYSTEM ERROR REPORT: {input}")                                        
    ])

    # Dynamic model vendor factory setup
    if provider == "openai":
        llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)
    else:
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, google_api_key=settings.GEMINI_API_KEY)

    structured_llm = llm.with_structured_output(OrchestratorAction)
        
    chain = prompt_template | structured_llm

    # Run the error analysis
    result = chain.invoke({
        "history": history_messages,
        "input": json.dumps(error_data) # Send the error dictionary here
    })


    with transaction.atomic():
        # Save a system note tracking user context alignment
        ChatMessage.objects.create(session=session, role="user", content=f"[System Error Handled: {json.dumps(error_data)}]")
        # Save the friendly question the LLM built
        ChatMessage.objects.create(session=session, role="ai", content=result.chat_response)

    # 📡 Broadcast the message down to the screen over WebSockets
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        channel_name,
        {
            "type": "chat_message",
            "payload": {
                "type": "orchestration_result",
                "raw_output": {"ui_layout_route": "CHAT", "chat_response": result.chat_response}
            }
        }
    )





@shared_task
def process_scan_payload_task(run_id, repository_owner, repo, tool, raw_content_str, save_to_db, repo_findings):
    task_debug_id = uuid.uuid4().hex[:8]
    print(
    f"\n⚡ CELERY START:{tool.upper()}] "
    f"id={task_debug_id} "
    f"tool={tool} "
    f"run={run_id}"
)
    
    try:
        findings = []
        total_issues = 0
        high_severity = 0
        loc = 0
        status = 'passed'

        # 1. 🎯 GLOBAL DEFENSIVE GATE: Determine if payload is clean JSON or a raw Crash Traceback
        is_json_format = False
        parsed_json = None
        
        try:
            parsed_json = json.loads(raw_content_str)
            is_json_format = True
        except json.JSONDecodeError:
            is_json_format = False
            print(f"⚠️ ALERT: {tool.upper()} payload is raw text (Possible infrastructure crash).")

        # CASE A: THE PAYLOAD IS A CRASH TRACEBACK (Any Tool)
        if save_to_db:
            findings.append(repo_findings)  # Append any existing findings from the error logs processed from the view
        # =====================================================================
        # 📦 CASE B: THE PAYLOAD IS CLEAN VALID JSON (Normal Behavior)
        # =====================================================================

        print(f"DEBUG: Parsed JSON content for {tool}: {save_to_db}")  # Debug print to inspect the structure of the parsed JSON
        if tool == 'bandit':
            totals = parsed_json.get('metrics', {}).get('_totals', {}) if parsed_json else {}
            loc = totals.get('loc', 0)
            high_severity = totals.get('SEVERITY.HIGH', 0)
            
            raw_results = parsed_json.get('results', []) if parsed_json else []
            total_issues = len(raw_results)
            status = 'failed' if high_severity > 0 else 'passed'
            
            for item in raw_results:
                findings.append({
                    'file': item.get('filename'),
                    'line': item.get('line_number'),
                    'name': item.get('test_id'),
                    'message': item.get('issue_text'),
                    'severity': item.get('issue_severity')
                })

        elif tool == 'ruff':
            # Ruff returns a flat list array of issue dicts when running --output-format json
            raw_results = parsed_json if isinstance(parsed_json, list) else []
            total_issues = len(raw_results)
            status = 'failed' if total_issues > 0 else 'passed'
            
            for item in raw_results:
                findings.append({
                    'file': item.get('filename'),
                    'line': item.get('location', {}).get('row'),
                    'name': item.get('code'),
                    'message': item.get('message'),
                    'severity': 'MEDIUM'
                })

        elif tool == 'odozi_visitors':
            raw_findings = parsed_json.get('findings', []) if parsed_json else []
            total_issues = len(raw_findings)
            status = 'failed' if total_issues > 0 else 'passed'
            
            for item in raw_findings:
                findings.append({
                    'file': './backend/task/views.py',
                    'line': item.get('line'),
                    'name': item.get('name'),
                    'message': item.get('message'),
                    'severity': 'HIGH' if item.get('rule') == 'missing_authentication' else 'LOW'
                })

        elif tool == 'pytest':
            print("pytest running")
            summary = parsed_json.get('summary', {}) if parsed_json else {}
            total_issues = summary.get('failed', 0)
            status = 'failed' if total_issues > 0 else 'passed'

        # =====================================================================
        # 🎯 OPTIMIZED MULTI-TENANT DB SAVE ENGINE (Single DB Trip)
        # =====================================================================
        workspace = Workspace.objects.get(name = repository_owner)

        repo_result, created = RepositoryScan.objects.update_or_create(
                run_id=run_id,
                tool=tool,
                defaults={
                    'repo': repo,
                    'workspace': workspace,
                    'status': status,
                    'total_issues': len(findings) if tool in ['pytest', 'ruff'] and is_json_format else total_issues,
                    'high_severity_count': high_severity,
                    'lines_of_code': loc,
                    'structured_findings': findings,
                    'raw_payload': parsed_json if is_json_format else {"log": raw_content_str}
                }
            )

            
        # Append chunks strictly for Pytest streams
        # if not created and tool == 'pytest' and not is_json_format:
        #     current_findings = repo_result.structured_findings or []
        #     for item in findings:
        #         if item not in current_findings:
        #             current_findings.append(item)
            
        #     old_log = repo_result.raw_payload.get("log", "") if isinstance(repo_result.raw_payload, dict) else ""
        #     repo_result.structured_findings = current_findings
        #     repo_result.total_issues = len(current_findings)
        #     repo_result.raw_payload = {"log": f"{old_log}\n{raw_content_str}"}
        #     repo_result.save()
        
        print(
            f"✅ CELERY DONE "
            f"id={task_debug_id}"
        )
        print(
            f"📡 WEBSOCKET SEND "
            f"tool={tool} "
            f"run={run_id}"
        )
    
    except Exception as e:
        print(f"❌ CRITICAL GENERAL TASK EXCEPTION: {str(e)}")







@shared_task
def cleanup_and_report(results, path):
    # Runing the transformation code
    clean_report = transform_ci_results(results)
    print(f"📝 [SIMPLIFIED REPORT]:\n{json.dumps(clean_report, indent=2)}")
    shutil.rmtree(path) # FINALLY delete the sandbox





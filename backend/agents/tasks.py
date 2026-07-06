import shutil
import traceback
import subprocess
import textwrap
import os
import re
import requests
import uuid
import json
import time
import jwt
import base64
import inspect
from toon import encode
from typing import cast

from celery import shared_task, group, chord

from .custom_functions.rules_library import LIBRARY
from .custom_functions.rules_registry import AST_TOOL_REGISTRY
from .custom_functions import rule_classes

from account_profile.models import GitHubRepository, Workspace
from django_python.schema import OrchestratorAction 

from odozi.service import create_workspace_with_repos


from django_python.models import RepositoryScan, RepoEnvKey,ChatSession, ChatMessage
from django.contrib.auth.models import User
from django_python.schema import OrchestratorAction

from django.conf import settings
from django.db import transaction
from django.core.cache import cache

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




def workflow_exists(url, headers, branch):
    response = requests.get(
        url,
        headers=headers,
        params={"ref": branch}
    )

    if response.status_code == 200:
        return {
            "exists": False,
            "sha": response.json().get("sha")
        }

    return {
        "exists": False,
        "sha": None
    }



def ensure_orchestrator_yaml_is_online(
    repo_owner,
    repo_name,
    default_branch,
    target_branch,
    git_token
):
    url = (
        f"https://api.github.com/repos/"
        f"{repo_owner}/{repo_name}/contents/"
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

    # ----------------------------------------------------
    # PARALLEL BRANCH CHECKS
    # ----------------------------------------------------

    with ThreadPoolExecutor(max_workers=2) as executor:

        default_future = executor.submit(
            workflow_exists,
            url,
            headers,
            default_branch
        )

        target_future = executor.submit(
            workflow_exists,
            url,
            headers,
            target_branch
        )

        default_result = default_future.result()
        target_result = target_future.result()

    # ----------------------------------------------------
    # ENSURE DEFAULT BRANCH
    # ----------------------------------------------------

    if not default_result["exists"]:

        payload = {
            "message": "ci: initialize Odozi workflow",
            "content": encoded_content,
            "branch": default_branch,
            "sha": default_result["sha"]
        }

        response = requests.put(
            url,
            json=payload,
            headers=headers
        )

        if response.status_code not in (200, 201):
            print(
                f"Default branch upload failed: "
                f"{response.status_code} {response.text}"
            )
            return False

    # ----------------------------------------------------
    # ENSURE TARGET BRANCH
    # ----------------------------------------------------

    if not target_result["exists"]:

        payload = {
            "message": "ci: initialize Odozi workflow",
            "content": encoded_content,
            "branch": target_branch,
            "sha": target_result["sha"]
        }

        response = requests.put(
            url,
            json=payload,
            headers=headers
        )

        if response.status_code not in (200, 201):
            print(
                f"Target branch upload failed: "
                f"{response.status_code} {response.text}"
            )
            return False

    print(
        f"Workflow present on "
        f"{default_branch} and {target_branch}"
    )

    return True



def get_installation_access_token(installation_id):
    """
    Uses your Private Key to mint a JWT, then exchanges it for a 
    short-lived 1-hour installation access token from GitHub.
    """
    # 1. Prepare the cryptographic JWT claims payload
    issued_at = int(time.time()) - 60  # Account for minor clock drifts (1 min ago)
    expires_at = issued_at + (10 * 60) # JWTs have a maximum lifetime limit of 10 minutes
    
    payload = {
        "iss": settings.ODOZI_APP_ID,  # Your GitHub App's unique identifier
        "iat": issued_at,
        "exp": expires_at,
    }
    

    # 2. Encode and sign the JWT using your multi-line RSA Private Key
    encoded_jwt = jwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")
    
    # 3. Request the temporary installation token from GitHub
    url = (
        f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    )
    headers = {
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",

        }
    
    response = requests.post(url, headers=headers)
    print("Status:", response.status_code)
    print("Response:", response.text)
    
    if response.status_code == 201:
        # Success: Returns a dictionary containing your temporary token string
        return response.json().get("token")
    else:
        raise Exception(f"Failed to generate installation token: {response.text}")



system_instruction_text = """
You are the AI Orchestrator Core for Project Odozi, an autonomous agentic CI/CD gateway. Your sole objective is to intercept a user's natural language project description or request, parse their intentions, and convert them into structured configuration variables inside our Pydantic action schema.

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
- Trigger Rules: If the user wants to evaluate code smells or style, assign "ruff" (generic linting). If they mention specific boundaries, map them to your native AST validators: "check_function_length" or "check_class_length".

4. PILLAR D: UNIT RUNNERS & CODE COVERAGE
- Keywords: "test", "pytest", "run tests", "coverage", "test percentage"
- Trigger Rules: If the user mentions testing, assign the strategy "pytest". If they explicitly mention tracking "coverage" or "percentage", you MUST include "pytest" and toggle your internal coverage flag fields.

5. GENERIC AST HOOK COGNITIVE SCAVENGERS
- Keywords: "transaction atomic", "db wrapper", "docstrings", "documentation comments"
- Trigger Rules: Map these precisely to "check_transaction_atomic" or "check_docstrings" using your parameters interface setup mapping block.

### CONTEXT EVOLUTION & HISTORY OVERHAUL PROTOCOL:
- For standard casual chats or technical inquiries, leave 'evict_prior_history' as False and 'condensed_history_summary' as None.
- The exact moment the user issues an operational execution command (e.g., "Run the first 2"), map the references to 'active_rules', set 'evict_prior_history' to True, and use your intelligence to populate 'condensed_history_summary'.
- Inside 'condensed_history_summary', extract ONLY the critical contextual baseline established prior to execution, combined with a record of the tools just launched. Strip all fluff, greetings, or basic question loops. 

Example Summary Output:
"User verified platform capabilities for pytest/bandit. Consolidated active workflow initiated for repo-b running strategy models: bandit, pytest."

### MANDATORY BRANCH CONFIGURATION & INTELLECTUAL MAPPING RULES:
1. When a user requests a tool execution run, look for branch context names in the text (e.g., 'main', 'master', 'test', 'new').
2. If the user provides a list of branches and repositories (e.g., repositories 'X and Y' and branches 'master, test, and new' or uses the word 'respectively'), use advanced contextual deduction to map the branches to the repositories sequentially. 
   - If 3 branches are provided for 2 active execution repositories, assign the first matching logical branches (e.g., Repository 1 -> 'master', Repository 2 -> 'test') or fallback intelligently.
3. If, and ONLY if, the user provides absolutely zero branch keywords anywhere in their message or historical context session baseline memory logs, you must:
   - Assign the smart engineering default branch "master" to the 'target_branch' field inside the Pydantic schema. 
   - Do NOT stop the pipeline or ask for clarification if a fallback default can keep the automation moving forward.
4. If a list of branches is completely incomprehensible and cannot be safely deduced, your 'chat_response' must intelligently ask for exact mapping layout structures (e.g., "I see you listed the branches 'master, test, and new'. To ensure exact execution, which branch applies to 'Taskmaster' and which applies to 'interview'?").

### INTENT PARSING AND MAPPING BOUNDARY RULES
- "create_workspace": Select this if the user wants to group fresh repositories under a brand new workspace container. Sanitized loose repository names (e.g., "repo a", "z") into standard layouts (e.g., "repo-a").
- "run_static_analysis": Select this intent ONLY if the user uses explicit, active commands ordering you to kick off, launch, run, or execute a test block run immediately (e.g., "Run pytest now", "Execute security audit"). You MUST populate the active_rules array mapping strategies to their target repositories.
- "technical_query": Select this intent if the user is asking a general question about options, capabilities, configurations, or checking what is possible without explicitly ordering a live execution run right now (e.g., "Can you run tests?", "How do I check types?"). When this intent is selected, the active_rules list MUST remain empty.
- Deduce smart engineering defaults if specific parameters or repository targets are omitted from the request context.

### UI LAYOUT CODES:
Set 'ui_layout_route' to:
- "CHAT": Conversational chat, questions, greetings, or branch clarifications.
- "CARD": Infrastructure changes (workspaces/repositories) with no testing tools.
- "TERM": Active CI/CD test runner pipelines (pytest, bandit, pip_audit, ruff, AST) are triggered.

"""






@shared_task
def parallel_handle_static_analysis_task(result_data, user_id, repo_owner):
    """
    🚀 TRUE INTENT PARALLELISM: This block now runs on its own independent worker thread.
    It handles all repository signature gathering and concurrent cloud dispatches
    without causing any lag to your database workspace creation steps!
    """
    pipeline_tasks = []

    # 1. Fetch and secure your repository cache guardrails layers defensively
    print(user_id)
    details_cache_key = f"user:repos:{user_id}"
    cached_details = cache.get(details_cache_key)
    
    if not cached_details or not isinstance(cached_details, dict):
        print(f"⚠️ Cache Miss or Invalid Type for key: {details_cache_key}. Falling back to standard processing.")
        cached_details = {}
        
    cached_repos = cached_details.get("repositories", {})
    cached_repos_set = set(cached_repos.get('repo_names', []))

    # 2. Extract tools and match parameters exactly as your stitching machine reads
    user_rules_payload = []
    for rule in result_data.get("active_rules", []):
        strategy = rule.get("strategy")
        if strategy not in ["pytest", "bandit", "pip_audit", "ruff"]:
            rule_params = getattr(rule, "params", {}) or {}
            user_rules_payload.append({
                "rule_key": strategy,
                "params": rule_params     
            })

    # 3. Loop through your rules list to build the parallel execution signature arrays
    for rule in result_data.get("active_rules", []):
        # Handle rule formatting checks securely
        rule_repo_name = rule.get("repo_name")
        
        if rule_repo_name in cached_repos_set:
            print("rule.repo_name", rule_repo_name)
            sanitized_name = rule_repo_name.lower().replace(" ", "-").strip()
            print("sanitized_name", sanitized_name)
            
            try:
                # Append the task signature context blocks to the array list
                pipeline_tasks.append(
                    run_agentic_pipeline.s( 
                        repo_owner=repo_owner,
                        repo_name=sanitized_name,
                        default_branch="main",
                        repo_data={},
                        commit_sha="main", 
                        target_branch=rule.get("target_branch") or "main",
                        ref_string=f"refs/heads/{rule.get('target_branch') or 'main'}",
                        installation_id="repo_obj.installation_id", 
                        user_requested_rules=user_rules_payload
                    )
                )
            except Exception:
                pass

    # 4. Fire all repository pipelines concurrently across your servers
    if pipeline_tasks:
        group(pipeline_tasks).apply_async()
        print(f"🎉 Bulk signature queue launched concurrently for {len(pipeline_tasks)} targets.")




@shared_task
def process_agentic_chat_turn_task(channel_name, user_id, session_id, prompt_text, repos, provider, model_name, api_key):
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
    for msg in past_messages:
        if msg.role == "user":
            history_messages.append(
                HumanMessage(content=msg.content)
            )
        elif msg.role == "ai":
            history_messages.append(
                AIMessage(content=msg.content)
            )

    # print("atitude")
    # toon_history_memory = encode(history_list)
    # print("iti")
    # print(history_list)
    # print("")
    # print(toon_history_memory)

    # master_system_prompt = f"""
    #     {system_instruction_text}

    #     ### PAST CONVERSATION STATE LOGS (TOON):
    #     {{toon_history}}
    # """

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

            print("\n🤖 ================== LLM FEEDBACK OBJECT ==================")
            print(f"🎯 DETECTED INTENTS: {result.intents}")
            if hasattr(result, 'chat_response') and result.chat_response:
                print(f"💬 CASUAL CHAT REPLY: {result.chat_response}")
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
                print(f"🔄 Database Overhaul Triggered: Purged casual history fluff for Session {session_id}.")
                
                # 2. Save the current user text prompt as the first record of the new era
                ChatMessage.objects.create(session=session, role="user", content=prompt_text)
                
                # 3. 🌱 THE SEED: Save the LLM's own high-utility condensed text summary
                # This becomes the single baseline row memory anchor for the next message turn!
                summary_marker = f"""
                    [ACTIVE SYSTEM CONTEXT BASELINE]:
                    The following infrastructure states were successfully verified and created by you in previous turns:
                    {result.condensed_history_summary}
                """
                ChatMessage.objects.create(session=session, role="ai", content=summary_marker)
                
                print("🌱 New memory baseline seed successfully planted in PostgreSQL history logs.")
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
        print("cached_repos", 44444444444, cached_details)
        # Check if data exists and is the correct format (list or dict of repos)
        if cached_details is not None:
            # Process your cached_repos directly here
            cached_repos = cached_details.get("repo_names", {})
            print(f"⚡ [CACHE HIT] Celery successfully loaded repositories for key: {cached_repos}")
        else:
            print(f"⚠️ Cache Miss for key: {details_cache_key}. Falling back to standard processing.")
            cached_repos = {}
        
        # 2. BuildIing concurrent execution canvas signature list array
        intent_signatures = []


        if "run_static_analysis" in result.intents:
            # 🚀 PASS THE CACHED REPO LIST DIRECTLY AS A PARAMETER!
            from celery import signature
            
            # 2. 🚀 THE TYPE-SAFE FIX: No square brackets used! 
            # You pass the task path name string and your parameters directly inside signature()
            serializable_rules = [rule.model_dump() for rule in result.active_rules]
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_static_analysis_task",
                    args=(serializable_rules, repo_owner, cached_repos) # 📥 Pass your variables as an ordered tuple
                )
            )

        if "create_workspace" in result.intents:
            # 🚀 PASS THE CACHED REPO LIST DIRECTLY AS A PARAMETER HERE TOO!
            from celery import signature
            
            # 2. 🚀 THE TYPE-SAFE FIX: No square brackets used! 
            # You pass the task path name string and your parameters directly inside signature()
            result_dict = result.model_dump()
            serializable_workspaces = result_dict.get('workspaces_to_create', [])
            cached_repositories = cached_details.get("repositories", [])
            intent_signatures.append(
                signature(
                    "agents.tasks.async_handle_workspace_creation_task",
                    args=(serializable_workspaces, user_id, cached_repositories) # 📥 Pass your variables as an ordered tuple
                )
            )


        # Fire both intent tasks concurrently in microseconds
        if intent_signatures:
            group(intent_signatures).apply_async()


        # -------------------------------------------------------------------------
        # PHASE 4: WEBSOCKET TRANSMISSION (Push data back up to the frontend UI)
        # -------------------------------------------------------------------------
        print("coat", "swaaaaa")
        
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
def async_handle_static_analysis_task(active_rules, repo_owner, parent_repo_list):
    """
    Runs in parallel. Reads the repo list straight out of RAM memory parameters,
    requiring ZERO outbound network connections to Redis!
    """
    # Convert the passed parameter directly into a lookup set array
    # print(,"parent_repo_list", parent_repo_list)
    print("active", active_rules,"saure", parent_repo_list)
    cached_repos_set = set(parent_repo_list)

    pipeline_tasks = []
    
    for rule in active_rules:
        print(f"rule.repo_name - {rule}")
        if rule.get('repo_name') in cached_repos_set:
            sanitized_name = rule.repo_name.lower().replace(" ", "-").strip()
            print(f"sanitized_name - {sanitized_name}")
            try:
                # Append the task signature context blocks to the array list
                pipeline_tasks.append(
                    run_agentic_pipeline.s( # 🌟 Note the '.s' signature decorator!
                        repo_owner=repo_owner,
                        repo_name=sanitized_name,
                        default_branch="main",
                        repo_data = {},
                        commit_sha="main", #work
                        target_branch=rule.target_branch or "main",
                        ref_string=f"refs/heads/{rule.target_branch}",
                        installation_id="repo_obj.installation_id", #work
                        user_requested_rules=rule.strategies
                    )
                )
            except GitHubRepository.DoesNotExist:
                pass


    # 🚀 BULK TRIGGER: Fire all task pipelines concurrently in microseconds!
    if pipeline_tasks:
        group(pipeline_tasks).apply_async()



@shared_task
def async_handle_workspace_creation_task(workspaces, user_id, parent_repo_list):
    """
    Runs in parallel with zero cache lag hooks.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    if not workspaces:
        return

    # 1. 🚀 FIX: Store the whole raw repo dict tied to its lowercase matching key
    # If parent_repo_list is just a list of strings, match the string directly
    print(type(parent_repo_list),"parent_repo_list", parent_repo_list)
    cached_pairs = [(repo.get('name', '').lower(), repo) for repo in parent_repo_list if isinstance(repo, dict)]

    
    workspace_list = workspaces if isinstance(workspaces, list) else [workspaces]

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

        # 3. Safe validation pass execution
        if len(repos_found) > 0:
            create_workspace_with_repos(user, ws_name, repos_found)
        else:
            print(f"ogbemudia - No repos found for workspace: {ws_name}")
            
    return "Workspace processing completed"




@shared_task
def run_agentic_pipeline(repo_owner, repo_name,default_branch, repo_data,commit_sha, target_branch,ref_string, installation_id, user_requested_rules):
    """
    Asynchronous platform dispatcher.
    """
    # =========================================================================
    # ✅ STEP 0: GENERATE DYNAMIC 1-HOUR TOKEN VIA PRIVATE KEY
    # =========================================================================
    try:
        # Trade installation_id + private key file for an active execution token
        git_token = get_installation_access_token(installation_id)
        print("SUCCESS: Fresh 1-hour installation token generated safely.")
    except Exception as e:
        print(f"CRITICAL: Token generation failed: {str(e)}")
        return {"status": "error", "message": "Authentication token exchange failure"}

    # =========================================================================
    # STEP 1: SCRIPT STITCHING ENGINE (Your existing logic)
    # =========================================================================
    ensure_orchestrator_yaml_is_online(repo_owner, repo_name, default_branch, target_branch, git_token)
    print("")
    print({"default_branch": default_branch, "commit_sha": commit_sha, "target_branch": target_branch, "ref_string": ref_string})
    base_classes_text = inspect.getsource(rule_classes)
    
    # Strip any local manual __main__ loop if it exists in your file text
    if 'if __name__ == "__main__":' in base_classes_text:
        base_classes_text = base_classes_text.split('if __name__ == "__main__":')[0].strip()

    visitor_instances_lines = []
    for rule in user_requested_rules:
        rule_key = rule["rule_key"]
        params = rule["params"]
        
        if rule_key in AST_TOOL_REGISTRY:
            class_name = AST_TOOL_REGISTRY[rule_key].__name__
            line = f"            {class_name}({json.dumps(params)}),"
            visitor_instances_lines.append(line)
            
    visitors_code_block = "\n".join(visitor_instances_lines)

    # DEBUG
    print(visitors_code_block)

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
                        
                        for visitor in visitors:
                            findings = visitor.analyze_file(full_path, code)
                            print(
                                visitor.__class__.__name__,
                                "found",
                                len(findings),
                                "issues in",
                                full_path
                            )
                            all_findings.extend(findings)
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
    print("user_requested_rules", user_requested_rules)
    selected_tools = user_requested_rules
     # 1. Look up the repository full slug name in your DB
    # repo_slug = f"{repo_owner}/{repo_name}"

    print(repo_name, repo_data, repo_owner, "repo")
    
    # 2. Fetch only the variable names registered for THIS specific repository
    repo_merge = f'{repo_owner}/{repo_name}'
    # repo_instance = GitHubRepository.objects.get(repo_name=repo_merge)
    registered_keys = RepoEnvKey.objects.filter(
         repo__repo_name=repo_merge
    ).values_list('key_name', flat=True)
    
    # Example output string: '["DJANO_SECRET_KEY"]'
    env_keys_payload = json.dumps(list(registered_keys)) if registered_keys else "[]"

    url = (
        f"https://api.github.com/repos/"
        f"{repo_owner}/{repo_name}/actions/workflows/"
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
            "tools_list": json.dumps(selected_tools),
            "custom_script_payload": encoded_script,
            "env_keys_list": env_keys_payload
        }
    }
    
    print("DEBUG: Dispatching to GitHub API with payload:")
    feedback_r = requests.post(url, json=api_payload, headers=headers)
    if feedback_r.status_code == 204:
        print("🎉 SUCCESS! GitHub successfully accepted the workflow dispatch request.")
        return {"status": "success", "message": "Pipeline launched successfully in the cloud."}
        
    else:
        # ✅ DEFENSIVE FIX: Print raw text instead of .json() to stop the JSONDecodeError crash
        print(f"❌ GITHUB ERROR [{feedback_r.status_code}]: {feedback_r.text}")
        return {
            "status": "validation_error", 
            "http_code": feedback_r.status_code, 
            "github_raw_message": feedback_r.text
        }




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





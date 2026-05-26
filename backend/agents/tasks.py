from celery import shared_task, group, chord
import shutil
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
from concurrent.futures import ThreadPoolExecutor
from .custom_functions.rules_library import LIBRARY
from .custom_functions.rules_registry import AST_TOOL_REGISTRY
from .custom_functions import rule_classes
from django.conf import settings
from django_python.models import RepositoryScan, RepoEnvKey
from account_profile.models import GitHubRepository, Workspace
from django.contrib.auth.models import User

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



def run_in_sandbox(path, command, image="python:3.11-slim"):
    # 1. Environment for the WORKER (to find docker)
    worker_env = {"PATH": os.environ.get("PATH")}

    # 2. Environment for the CONTAINER (to harden the tool)
    docker_cmd = [
        "docker", "run", "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--net", "none",
        "-e", "PYTEST_ADDOPTS=-c /dev/null",  # <--- Passed into the sandbox
        "-e", "HOME=/tmp",                   # <--- Passed into the sandbox
        "-v", f"{path}:/app",
        "-w", "/app",
        image,
        *command
    ]
    
    result = subprocess.run(docker_cmd, env=worker_env, capture_output=True, text=True)
    
    # --- THE SENIOR DEBUG LAYER ---
    # print(f"📦 [DOCKER STATUS]: Exited with code {result.returncode}")
    # if result.stdout:
    #     print(f"📄 [DOCKER STDOUT]:\n{result.stdout.strip()}")
    # if result.stderr:
    #     print(f"🛑 [DOCKER STDERR]:\n{result.stderr.strip()}")
    # print("═" * 50)
    # 2. YOU MUST CONVERT IT TO A DICTIONARY HERE:
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }




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



@shared_task(bind=True, autoretry_for=(requests.exceptions.ConnectionError,), retry_backoff=True)
def run_pytest(self, path):
    """
    Runs pytest in the specified sandbox directory.
    """
    try:
        # 1. Run the command
        # we use 'universal_newlines' to get string output instead of bytes
        safe_env = {
            "PATH": os.environ.get("PATH"),
            "HOME": "/tmp",
            "PYTEST_ADDOPTS": "-c /dev/null" # Prevents pytest from reading global configs
        }

        result = subprocess.run(
            ["pytest", "--json-report", "--json-report-file=report.json", "--cov=.", "--cov-report=json"], 
            cwd=path,               # Run inside the sandbox folder
            env=safe_env,
            capture_output=True, 
            text=True,
            timeout=300             # 5 minute timeout safety net
        )

        # 2. Check the exit code, 0 = All tests passed, 1 = Tests failed, Others = System/No tests found error
        if result.returncode == 0:
            status = "passed"
        elif result.returncode == 1:
            status = "failed"
        else:
            status = "System Error or No tests found Error"

        return {
            "tool": "pytest",
            "status": status,
            "stdout": result.stdout[-2000:], # Return last 2000 chars of logs
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        return {"tool": "pytest", "status": "error", "message": "Timed out after 5 mins"}
    # except Exception as e:
    #     # If it's a transient error, retry!
    #     raise self.retry(exc=e)



@shared_task
def run_lint_check(path):
    """
    Checks for code quality using Ruff inside an isolated container.
    """

    # Dynamically install ruff, then execute the check
    # command = ["sh", "-c", "pip install --quiet ruff && ruff check --format json ."]
    command = ["ruff", "check", "--output-format", "json", "."]
    
    # 1. Check for errors
    response = run_in_sandbox(path, command, image="odozi-tools:latest") # Use a pre-built image with ruff installed
    
    # if response["exit_code"] != 0:
    #     # 2. Run the fix in the sandbox
    #     run_in_sandbox(path, ["ruff", "check", "--fix", "."])
        
    #     # 3. Get the DIFF (This is the 'Senior' part)
    #     # We ask git: "What did the linter just change?"
    #     diff_result = subprocess.run(
    #         ["git", "diff"], cwd=path, capture_output=True, text=True
    #     )
        
    #     return {
    #         "tool": "linter",
    #         "status": "failed_but_fixable",
    #         "fix_suggestion": diff_result.stdout, # <--- Pass this to the LLM/UI
    #         "summary": "Found style issues. Suggested fixes are available."
    #     }
    status = "passed" if response["exit_code"] == 0 else "failed"

    errors = response["stdout"] if response["stdout"] else response["stderr"]

    
    return {
        "tool": "linter",
        "status": status,
        "errors_found": errors,
        "summary": "Code format is clean" if status == "passed" else "Linting errors detected"
    }



@shared_task
def run_security_scan(path):
    """
    Scans for security vulnerabilities using Bandit.
    """
    # -lll: Only show high-severity issues
    # -f json: Easy for our Agent to parse
    command = ["bandit", "-r", ".", "-lll", "-f", "json"]
    
    # This command handles installation and execution sequentially inside the container
    # command = ["sh", "-c", "pip install --quiet bandit && bandit -r . -lll -f json"]
    
    # We can use a basic python image with bandit installed
    response = run_in_sandbox(path, command, image="odozi-tools:latest") # Use a pre-built image with bandit installed
    
    # Bandit returns exit code 1 if it finds vulnerabilities
    status = "passed" if response["exit_code"] == 0 else "failed"
    errors = response["stdout"] if response["stdout"] else response["stderr"]
    
    return {
        "k":"k"
        # "tool": "security_scan",
        # "status": status,
        # "vulnerabilities": errors,
        # "summary": "Security scan cleared" if status == "passed" else "Vulnerabilities detected!"
    }



@shared_task
def run_custom_semgrep(path, yaml_rule_text):
    rule_filename = f"rule_{uuid.uuid4().hex[:8]}.yaml"
    rule_path = os.path.join(path, rule_filename)

    try:
        with open(rule_path, "w") as f:
            f.write(yaml_rule_text)

        # Optimization: We keep the scanning target dot at the absolute end
        command = [
            "semgrep", "scan",
            "--config", rule_filename, 
            "--json", 
            "--skip-unknown-extensions", 
            "--quiet",
            "--force-color",  # <-- Add this flag here to disable Git path locks
            "/app"  # <-- Explicitly scan the /app mount inside Docker not path nor root . 
        ]        
        response = run_in_sandbox(path, command, image="odozi-tools:latest")

        findings = []
        system_errors = []

        # Parse response safely
        if response["stdout"].strip():
            try:
                full_output = json.loads(response["stdout"])
                findings = full_output.get("results", [])
                system_errors = full_output.get("errors", [])
            except json.JSONDecodeError:
                system_errors = [{"system_error": response["stdout"].strip()}]
        else:
            # If stdout is empty check if stderr contained actual system crashes
            if response["stderr"].strip():
                system_errors = [{"system_stderr": response["stderr"].strip()}]

        # FIXED SCOPE: This execution tracking line is now safe and runs unconditionally
        status = "failed" if (findings or system_errors) else "passed"

        return {
            "tool": "semgrep_custom",
            "findings": findings,
            "status": status,
            "errors": system_errors,
        }

    finally:
        if os.path.exists(rule_path):
            os.remove(rule_path)



# @shared_task
# def run_mypy_check(path):
#     """
#     Validates Python strict typing consistency inside the sandbox.
#     """
#     # --hide-error-context keeps the output brief and easy to parse
#     command = ["mypy", ".", "--hide-error-context", "--no-error-summary"]
    
#     response = run_in_sandbox(path, command, image="odozi-tools:latest")
    
#     status = "passed" if response["exit_code"] == 0 else "failed"
#     errors = response["stdout"] if response["stdout"] else response["stderr"]

#     return {
#         "tool": "mypy_type_check",
#         "status": status,
#         "errors_found": errors,
#         "type_errors": response["stdout"].strip().split("\n") if response["stdout"] else [],
#         "summary": "Type signatures are completely consistent" if status == "passed" else "Type safety deviations found"
#     }


@shared_task
def run_mypy_check(path):
    """
    Pure Python Governance Checker: Enforces that all functions and methods 
    implement explicit type annotations for parameter arguments and return paths.
    """
    import ast
    
    type_errors = []
    
    for root, dirs, files in os.walk(path):
        # Scan only your core codebase files
        if "venv" in root or ".git" in root or "migrations" in root:
            continue
            
        for file in files:
            # Explicitly skip framework entrypoints
            if file == "manage.py" or file == "wsgi.py" or file == "asgi.py":
                continue
            
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                relative_file_path = os.path.relpath(full_path, path)
                
                with open(full_path, "r") as f:
                    try:
                        tree = ast.parse(f.read())
                    except SyntaxError:
                        continue
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Avoid checking standard class constructor setups
                        if node.name == "__init__":
                            continue
                            
                        # Rule A: Validate Return Path Annotations
                        if not node.returns:
                            type_errors.append({
                                "file": relative_file_path,
                                "line": node.lineno,
                                "function": node.name,
                                "error": "Function is missing an explicit return type annotation (e.g., -> None or -> Response)."
                            })
                            
                        # Rule B: Validate Input Argument Annotations
                        for arg in node.args.args:
                            if arg.arg == "self" or arg.arg == "cls" or arg.arg == "request":
                                continue
                            if not arg.annotation:
                                type_errors.append({
                                    "file": relative_file_path,
                                    "line": node.lineno,
                                    "function": node.name,
                                    "error": f"Argument '{arg.arg}' is missing an explicit type hint annotation."
                                })

    status = "failed" if type_errors else "passed"
    
    return {
        "tool": "mypy_type_check",
        "status": status,
        "type_errors": type_errors,
        "summary": "Type signatures are completely compliant" if status == "passed" else f"Found {len(type_errors)} unannotated execution points"
    }



@shared_task
def run_secret_scanning(path):
    """
    Scans the repository for hardcoded passwords, tokens, and private keys.
    """
    # This regex means: Exclude any file that does NOT end in .py OR is named manage.py
    exclude_regex = r"^(?!.*\.py$)|.*manage\.py$"
    
    command = [
        "detect-secrets", "scan", 
        "--exclude-files", exclude_regex
    ]
    # detect-secrets scans the folder and outputs a clean JSON structure
    response = run_in_sandbox(path, command, image="odozi-tools:latest")
    
    status = "passed"
    findings = {}
    
    if response["stdout"].strip():
        try:
            full_output = json.loads(response["stdout"])
            # Extract only the explicit credential leaks found across files
            findings = full_output.get("results", {})
            if findings:
                status = "failed"
        except json.JSONDecodeError:
            status = "failed"
            findings = {"system_error": "Failed to parse detect-secrets output"}
    errors = response["stdout"] if response["stdout"] else response["stderr"]

    return {
        "tool": "secret_scanner",
        "status": status,
        "leaked_secrets": findings,
        "errors_found": errors,
        "summary": "No exposed credentials detected" if status == "passed" else "Critical: Exposed credentials detected!"
    }


@shared_task
def run_migration_check(path):
    """
    Pure Python Migration Check: Looks for modified model files 
    that lack corresponding incremental migration records.
    """
    import ast
    
    violations = []
    
    # 1. Scan the directory path for Django apps
    for root, dirs, files in os.walk(path):
        if "models.py" in files and "migrations" in dirs:
            models_file = os.path.join(root, "models.py")
            migrations_dir = os.path.join(root, "migrations")
            
            # 2. Extract model class names using AST
            with open(models_file, "r") as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                    
            model_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if the class inherits from models.Model
                    for base in node.bases:
                        if isinstance(base, ast.Attribute) and base.attr == "Model":
                            model_names.append(node.name)
                        elif isinstance(base, ast.Name) and base.id == "Model":
                            model_names.append(node.name)

            # 3. Read the contents of the migrations folder
            migration_files = [f for f in os.listdir(migrations_dir) if f.endswith(".py") and f != "__init__.py"]
            
            combined_migration_content = ""
            for mf in migration_files:
                with open(os.path.join(migrations_dir, mf), "r") as f:
                    combined_migration_content += f.read()

            # 4. CRITERIA: If a model class exists but its name isn't found in any migration file
            for model in model_names:
                if f"name='{model}'" not in combined_migration_content and f"'{model}'" not in combined_migration_content:
                    violations.append({
                        "app": os.path.basename(root),
                        "model": model,
                        "message": f"Model '{model}' is defined in models.py but has no matching tracking state record inside the migrations folder."
                    })

    status = "failed" if violations else "passed"
    
    return {
        "tool": "migration_consistency",
        "status": status,
        "violations": violations,
        "summary": "All local database schema definitions are properly recorded" if status == "passed" else f"Detected {len(violations)} missing migrations."
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



@shared_task
def run_ci_suite(path, actions):
    job_list = []

    # 1. Add parallel legacy checkers to queue
    if actions.get("run_lint"):
        job_list.append(run_lint_check.s(path))
    if actions.get("check_security"):
        job_list.append(run_security_scan.s(path))

    if actions.get("run_mypy"):
        job_list.append(run_mypy_check.s(path))
    if actions.get("scan_secrets"):
        job_list.append(run_secret_scanning.s(path))
    if actions.get("check_migrations"):
        job_list.append(run_migration_check.s(path))

    # 2. Build the unified Semgrep rules block safely
    constraints_to_run = user_payload.get("constraints", [])
    combined_yaml = "rules:\n"
    has_custom_rules = False
    
    for item in constraints_to_run:
        rule_type = item.get("type")
        params = item.get("params", {})

        if rule_type in LIBRARY:
            has_custom_rules = True
            raw_template = LIBRARY[rule_type]
            formatted_rule = raw_template.format(**params)
            
            rule_lines = formatted_rule.strip().split("\n")
            for line in rule_lines:
                if not line.strip().startswith("rules:"):
                    combined_yaml += f"{line}\n"
    
    # 3. Append the unified Semgrep task signature to the central Chord collection
    if has_custom_rules:
        job_list.append(run_custom_semgrep.s(path, combined_yaml))

    if not job_list:
        return "No tasks to execute"
    
    # 4. Fire off all tools in parallel. The aggregator will capture all findings!
    callback = cleanup_and_report.s(path)
    workflow = chord(job_list)(callback)
    
    print("🔥 [CELERY MANAGER] Parallel fan-out complete. Running tools.")
    return "Workflow Started"



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
    print("RULES:", user_requested_rules)
    print("VISITORS:")
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
    selected_tools = ["pytest", "ruff", "bandit", "odozi_visitors"]
     # 1. Look up the repository full slug name in your DB
    # repo_slug = f"{repo_owner}/{repo_name}"

    print(repo_name, repo_data, repo_owner, "repo")
    
    # 2. Fetch only the variable names registered for THIS specific repository
    repo_merge = f'{repo_owner}/{repo_name}'
    repo_instance = GitHubRepository.objects.get(repo_name=repo_merge)
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
def process_scan_payload_task(run_id, repository_owner, repo, tool, raw_content_str):
    print(f"\n⚡ --- [CELERY JOB RECEIVED: {tool.upper()}] ---")
    
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

        # =====================================================================
        # 🛡️ CASE A: THE PAYLOAD IS A CRASH TRACEBACK (Any Tool)
        # =====================================================================
        if not is_json_format:
            status = 'failed'
            total_issues = 1
            
            # Use Regex to see if it's an infrastructure/environment issue or code syntax
            if "UndefinedValueError" in raw_content_str or "KeyError" in raw_content_str:
                msg = "Runtime infrastructure configuration error: Missing required environment variables."
            elif "SyntaxError" in raw_content_str:
                msg = "Code execution blocked: Severe Python syntax error detected in repository code."
            else:
                msg = f"Internal execution failure: The tool container terminated unexpectedly during analysis."

            findings.append({
                "status": "tool_crash",
                "variable": "SYSTEM",
                "message": msg
            })

        # =====================================================================
        # 📦 CASE B: THE PAYLOAD IS CLEAN VALID JSON (Normal Behavior)
        # =====================================================================
        else:
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
        if not created and tool == 'pytest' and not is_json_format:
            current_findings = repo_result.structured_findings or []
            for item in findings:
                if item not in current_findings:
                    current_findings.append(item)
            
            old_log = repo_result.raw_payload.get("log", "") if isinstance(repo_result.raw_payload, dict) else ""
            repo_result.structured_findings = current_findings
            repo_result.total_issues = len(current_findings)
            repo_result.raw_payload = {"log": f"{old_log}\n{raw_content_str}"}
            repo_result.save()

        print(f"🎉 SUCCESS: Sync Complete. Tool: {repo_result.tool} | Created: {created} | Total Issues Saved: {repo_result.total_issues}")

    except Exception as e:
        print(f"❌ CRITICAL GENERAL TASK EXCEPTION: {str(e)}")




@shared_task
def cleanup_and_report(results, path):
    # Runing the transformation code
    clean_report = transform_ci_results(results)
    print(f"📝 [SIMPLIFIED REPORT]:\n{json.dumps(clean_report, indent=2)}")
    shutil.rmtree(path) # FINALLY delete the sandbox





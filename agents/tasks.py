from celery import shared_task, group, chord
import shutil
import subprocess
import os
import requests
# Celery tasks (the parallel tools)




def run_in_sandbox(path, command, image="python:3.11-slim"):
    # 1. Environment for the WORKER (to find docker)
    worker_env = {"PATH": os.environ.get("PATH")}

    # 2. Environment for the CONTAINER (to harden the tool)
    docker_cmd = [
        "docker", "run", "--rm",
        "--net", "none",
        "-e", "PYTEST_ADDOPTS=-c /dev/null",  # <--- Passed into the sandbox
        "-e", "HOME=/tmp",                   # <--- Passed into the sandbox
        "-v", f"{path}:/app",
        "-w", "/app",
        image,
        *command
    ]
    
     # 1. Capture the raw execution result
    result = subprocess.run(docker_cmd, env=worker_env, capture_output=True, text=True)
    print(f"📦 [DOCKER ENGINE] Container process exited with code: {result.returncode}")
    # 2. YOU MUST CONVERT IT TO A DICTIONARY HERE:
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
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
            ["pytest", "--json-report", "--json-report-file=report.json"], 
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
    command = ["sh", "-c", "pip install --quiet ruff && ruff check --format json ."]
    
    # 1. Check for errors
    response = run_in_sandbox(path, command, image="python:3.12-slim")
    # initial_check = run_in_sandbox(path, ["ruff", "check", "."])
    
    if response["exit_code"] != 0:
        # 2. Run the fix in the sandbox
        run_in_sandbox(path, ["ruff", "check", "--fix", "."])
        
        # 3. Get the DIFF (This is the 'Senior' part)
        # We ask git: "What did the linter just change?"
        diff_result = subprocess.run(
            ["git", "diff"], cwd=path, capture_output=True, text=True
        )
        
        return {
            "tool": "linter",
            "status": "failed_but_fixable",
            "fix_suggestion": diff_result.stdout, # <--- Pass this to the LLM/UI
            "summary": "Found style issues. Suggested fixes are available."
        }
    
    return {"tool": "linter", "status": "passed"}


@shared_task
def run_security_scan(path):
    """
    Scans for security vulnerabilities using Bandit.
    """
    # -lll: Only show high-severity issues
    # -f json: Easy for our Agent to parse
    command = ["bandit", "-r", ".", "-lll", "-f", "json"]
    
    # We can use a basic python image with bandit installed
    response = run_in_sandbox(path, command, image="python:3.12-slim")
    
    # Bandit returns exit code 1 if it finds vulnerabilities
    status = "passed" if response["exit_code"] == 0 else "failed"
    
    return {
        "tool": "security_scan",
        "status": status,
        "vulnerabilities": response["stdout"], # JSON list of issues
        "summary": "No critical vulnerabilities found" if status == "passed" else "Critical issues detected!"
    }



@shared_task
def run_ast_test(path):
    # Logic to run AST analysis
    return {"tool": "ast_test", "result": "no issues"}

@shared_task
def run_code_in_a_container(path):
    # Logic to run code in a container
    return {"tool": "container", "result": "passed"}

@shared_task
def run_ci_suite(path, actions):
    # Create a list of tasks based on what the LLM said
    job_list = []
    # if actions.get("run_tests"):
    #     job_list.append(run_pytest.s(path))
    if actions.get("run_lint"):
        job_list.append(run_lint_check.s(path))
    if actions.get("check_security"):
        job_list.append(run_security_scan.s(path))
    if actions.get("check_ast"):
        job_list.append(run_ast_test.s(path))
    if actions.get("run_in_container"):
        job_list.append(run_code_in_a_container.s(path))
    
     # Chord: (Group of tasks) | (Final task to run at the end)
    callback = cleanup_and_report.s(path)
    workflow = chord(job_list)(callback)
    print("🔥 [CELERY MANAGER] Fan-out complete. Parallel processes running.")
    print(f"📊 [CELERY MANAGER] Current workflow state: {workflow}")
    return "Workflow Started"



@shared_task
def cleanup_and_report(results, path):
    # 'results' is a list of outputs from all parallel tools
    print("🏁 [CELERY AGGREGATOR] All parallel sandboxes closed. Collecting results...")
    print(f"📝 [SUMMARY REPORT]:\n{results}")  
    print(f"🧹 [CLEANUP] Destroying ephemeral path: {path}")
    shutil.rmtree(path) # FINALLY delete the sandbox

# @shared_task
# def cleanup_and_report(results, path):
#     # 'results' looks like: [{"tool": "pytest", "status": "passed"}, {"tool": "security", ...}]
#     for report in results:
#         if report['status'] == 'failed':
#             print(f"Alert: {report['tool']} found issues!")
    
#     # Now safe to delete
#     shutil.rmtree(path)



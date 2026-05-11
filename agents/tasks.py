from celery import shared_task, group, chord
import shutil
import subprocess
import os
import requests
# Celery tasks (the parallel tools)

@shared_task(bind=True, autoretry_for=(requests.exceptions.ConnectionError,), retry_backoff=True)
def run_pytest(self, path):
    """
    Runs pytest in the specified sandbox directory.
    """
    try:
        # 1. Run the command
        # we use 'universal_newlines' to get string output instead of bytes
        result = subprocess.run(
            ["pytest", "--json-report", "--json-report-file=report.json"], 
            cwd=path,               # Run inside the sandbox folder
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
def run_security_check(path):
    # Logic to run 'bandit' or security tools
    return {"tool": "security", "result": "no issues"}

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
    if actions.get("run_tests"):
        job_list.append(run_pytest.s(path))
    if actions.get("check_security"):
        job_list.append(run_security_check.s(path))
    if actions.get("check_ast"):
        job_list.append(run_ast_test.s(path))
    if actions.get("run_in_container"):
        job_list.append(run_code_in_a_container.s(path))
    
     # Chord: (Group of tasks) | (Final task to run at the end)
    callback = cleanup_and_report.s(path)
    workflow = chord(job_list)(callback)
    return "Workflow Started"

@shared_task
def cleanup_and_report(results, path):
    # 'results' is a list of outputs from all parallel tools
    print(f"All tools finished: {results}")
    shutil.rmtree(path) # FINALLY delete the sandbox


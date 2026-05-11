# agents/orchestrator.py
from .services.git_service import CIWorkspace
from .tasks import run_ci_suite
# from .tasks import run_parallel_checks # This would be your Celery group
# from .services.llm_service import analyze_diff_with_llm


'''
remove the numbers in the comments and rewrite every comment that suggests that AI is giving me advice to look like am advicing myself, eg-        # Pass ws.root_dir to your tools so they know where to run
, changes to         # Passing ws.root_dir to my tools so they know where to run
'''


def start_agentic_workflow(repo_url, branch):
    # 1. Setup workspace (Manual creation since Celery needs it to persist)
    ws = CIWorkspace(repo_url, branch)
    ws.setup_persistent_folder() # Create folder and clone
    
    # 2. Get the diff and ask the LLM for the plan
    diff = ws.get_diff()
    # actions_json = analyze_diff_with_llm(diff) 
    # Example actions: {"run_tests": true, "check_security": true, ...}
    actions_json = {"run_tests": True, "check_security": True}

    # 3. CALLING THE TASK
    # Use .delay() to push the job to Redis. 
    # The worker will pick up 'run_ci_suite' and then fan out the tools.
    run_ci_suite.delay(ws.root_dir, actions_json)

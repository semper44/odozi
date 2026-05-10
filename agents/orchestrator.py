# agents/orchestrator.py
from .services.git_service import CIWorkspace
from .tasks import run_parallel_checks # This would be your Celery group


'''
remove the numbers in the comments and rewrite every comment that suggests that AI is giving me advice to look like am advicing myself, eg-        # Pass ws.root_dir to your tools so they know where to run
, changes to         # Passing ws.root_dir to my tools so they know where to run
'''


def start_ci_pipeline(repo_url, pr_branch):
    # 1. Setup Sandbox & Clone
    with CIWorkspace(repo_url, pr_branch) as ws:
        # 2. Get the Diff for the LLM
        code_diff = ws.get_diff(base_branch="main")
        
        # 3. Analyze with LLM (to decide which tools to run)
        # actions = llm.extract_actions(code_diff) 
        
        # 4. Trigger Parallel Tools
        # Pass ws.root_dir to your tools so they know where to run
        print(f"Running checks on: {code_diff[:100]}...") # Short preview
        
        # NOTE: In a real Celery setup, you'd move the cleanup 
        # to the 'Aggregate' task so the tools have time to work.

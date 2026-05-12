# agents/orchestrator.py
from .services.git_services import CIWorkspace
from .tasks import run_ci_suite
# from .tasks import run_parallel_checks # This would be your Celery group
# from .services.llm_service import analyze_diff_with_llm


'''
remove the numbers in the comments and rewrite every comment that suggests that AI is giving me advice to look like am advicing myself, eg-        # Pass ws.root_dir to your tools so they know where to run
, changes to         # Passing ws.root_dir to my tools so they know where to run
'''


def start_agentic_workflow(repo_url, branch, base_branch="main"):
    # 1. Setup workspace (Manual creation since Celery needs it to persist)
    ws = CIWorkspace(repo_url, branch)
    print("🚀 [ORCHESTRATOR] Initializing secure git workspace...")
    ws.setup_persistent_folder() # Create folder and clone
    print(f"✅ [ORCHESTRATOR] Clone complete! Repository hosted at: {ws.root_dir}")

    
    # 2. Get the diff and ask the LLM for the plan
    # actions_json = analyze_diff_with_llm(diff) 
    # Example actions: {"run_tests": true, "check_security": true, ...}
    try:
        # Pass the user-defined base branch into the diff logic
        diff = ws.get_diff(base_branch=base_branch)
        # print(f"📊 diff {diff}...")
        
        actions_json = {"run_tests": True, "check_security": True, "run_lint": True, "check_ast":True} # Placeholder for LLM output
        # 3. CALLING THE TASK
        # Use .delay() to push the job to Redis. 
        # The worker will pick up 'run_ci_suite' and then fan out the tools.
        print("📨 [ORCHESTRATOR] Handoff to Celery Worker pool initiated.")
        run_ci_suite.delay(ws.root_dir, actions_json)
        return {"status": "success", "message": "Pipeline started"}    

    except Exception as e:
        print(f"❌ [ORCHESTRATOR] Pipeline execution failed: {str(e)}")
        # If git fails, clean up the workspace immediately and pass the error back
        import shutil
        if ws.root_dir:
            shutil.rmtree(ws.root_dir)
        return {"status": "error", "message": str(e)}


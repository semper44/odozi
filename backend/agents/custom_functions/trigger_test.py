# trigger_test.py
from agents.tasks import run_agentic_pipeline

# Mock user data to test your dynamic rule builder logic
mock_user_rules = [
    {
        "rule_key": "check_auth", 
        "params": {"function_prefix": "api_", "decorator_name": "login_required"}
    },
    {
        "rule_key": "check_function_length", 
        "params": {"keyword": "fetch", "max_lines": 50}
    }
]

# Use .apply() to execute the code synchronously on your screen right now
print("Invoking pipeline synchronously...")
run_agentic_pipeline.apply(
    args=("mock_owner", "mock_repo", "mock_token", "mock_sha", mock_user_rules)
)

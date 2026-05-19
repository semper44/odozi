import base64
import os
import requests
from django.conf import settings

def install_orchestrator_yaml(repo_owner, repo_name, git_token, target_branch="main"):
    """
    Programmatically injects the orchestrator.yaml file into the user's 
    repository using the GitHub Contents API.
    """
    # 1. Target endpoint for writing a file into a specific repository path
    url = f"github.com{repo_owner}/{repo_name}/contents/.github/workflows/orchestrator.yaml"
    
    # 2. Read your master template file from your Django project storage
    template_path = os.path.join(settings.BASE_DIR, 'agents', 'templates', 'orchestrator.yaml')
    with open(template_path, 'r', encoding='utf-8') as f:
        yaml_content = f.read()
        
    # 3. GitHub demands file content payloads be sent as raw Base64 strings
    encoded_bytes = base64.b64encode(yaml_content.encode('utf-8'))
    base64_yaml = encoded_bytes.decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {git_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "message": "ci: install agentic testing orchestrator blueprint", # Git commit message
        "content": base64_yaml,                                         # Base64 string payload
        "branch": target_branch                                         # Target branch
    }
    
    # 4. Check if file already exists to avoid throwing unhandled error states
    check_response = requests.get(url, headers=headers)
    if check_response.status_code == 200:
        # File is already safely installed in their repo, exit cleanly!
        return True
        
    # 5. Make the PUT request to physically write the file to their GitHub repository
    response = requests.put(url, json=payload, headers=headers)
    
    # Returns True if created successfully (201 Created status code)
    return response.status_code == 201

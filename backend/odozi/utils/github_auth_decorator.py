from functools import wraps
import requests
from django.http import JsonResponse

from account_profile.models import GitHubRepository

def require_github_auth(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Extract the temporary GITHUB_TOKEN sent by the runner
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Missing authentication metadata'}, status=401)
        
        github_token = auth_header.split(' ')[1]
        
        # 2. Validate the token directly against GitHub's official API
        # Using the standard repository repository validation endpoint
        print("request.POST")
        print("")
        print(request.POST)
        # Inside your security decorator / view logic
        # repo_full_name = request.POST.get('repo') # e.g., "OdoziEngine/Taskmaster"

        # try:
        #     # 1. Instantly find the repo and its parent workspace in one database query
        #     repo = GitHubRepository.objects.select_related('workspace').get(repo_full_name=repo_full_name)
        #     target_workspace = repo.workspace
            
        #     # 2. You now have instant access to the App Installation details securely!
        #     current_installation_id = target_workspace.installation_id
            
        # except GitHubRepository.DoesNotExist:
        #     return JsonResponse({'error': 'Repository not integrated with any workspace'}, status=404)


        repo_name = request.POST.get('repo') # e.g., "username/project"
        github_api_url = f"https://github.com/{repo_name}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(github_api_url, headers=headers)
        
        # If GitHub rejects the token, block the request immediately
        if response.status_code != 200:
            return JsonResponse({'error': 'Invalid or expired GitHub runner token'}, status=403)
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view

import json
import requests
from functools import wraps
from django.http import JsonResponse

from account_profile.models import GitHubRepository


def require_github_auth(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Extract the temporary GITHUB_TOKEN sent by the runner
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Missing authentication metadata'}, status=401)
        
        try:
            github_token = auth_header.split(' ')[1]
        except IndexError:
            return JsonResponse({'error': 'Malformed authorization token string'}, status=401)
        
        # 2. ✅ HIGH-LEVEL FIX: Extract repo layout dynamically based on content encoding
        repo_name = None
        if request.content_type == 'application/json':
            try:
                # Read the payload from request.body for JSON streams
                body_data = json.loads(request.body.decode('utf-8'))
                repo_name = body_data.get('repo')
            except Exception:
                return JsonResponse({'error': 'Invalid JSON stream encoding'}, status=400)
        else:
            # Read from standard POST data fields for multipart form uploads
            repo_name = request.POST.get('repo')

        if not repo_name:
            return JsonResponse({'error': 'Missing target repository context parameters'}, status=400)
       
        # 3. Request confirmation from GitHub's validation servers
        github_api_url = f"https://github.com/{repo_name}" # ◄— Points to official REST validation path
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            response = requests.get(github_api_url, headers=headers, timeout=5)
            if response.status_code != 200:
                return JsonResponse({'error': 'Invalid or expired GitHub runner token'}, status=403)
        except requests.RequestException as e:
            return JsonResponse({'error': f'Auth server communication breakdown: {str(e)}'}, status=502)
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


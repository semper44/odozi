import json
import uuid
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from agents.tasks import process_scan_payload_task
from account_profile.models import GitHubRepository, Workspace
from .models import UserProfileModel
from odozi.utils.crypto import decrypt_token  
from odozi.utils.security import verify_signature
from odozi.utils.github_auth_decorator import require_github_auth
from .serializer import GitHubRepositorySerializer, UserProfileSerializer

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync





def dashboard_view(request):
    """
    API endpoint that returns user repositories directly as JSON to the React frontend.
    Reads identity securely from the incoming HttpOnly cookie state.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # 1. Resolve token from incoming cookies (No longer relying strictly on request.user session)
    access_token_cookie = request.COOKIES.get("github_access_token")
    if not access_token_cookie:
        return JsonResponse({"error": "Unauthorized: Active session cookie missing"}, status=401)

    # Convert bytes to string safely if needed
    access_token = access_token_cookie.decode("utf-8") if isinstance(access_token_cookie, bytes) else access_token_cookie

    # 2. Request your repositories directly from GitHub's data server
    repos_url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        response = requests.get(repos_url, headers=headers, params={"per_page": 100, "sort": "updated"}, timeout=5.0)
        if response.status_code != 200:
            return JsonResponse({"error": "Failed to fetch data from GitHub API"}, status=response.status_code)
            
        repositories_data = response.json()
    except requests.RequestException:
        return JsonResponse({"error": "GitHub connectivity failure"}, status=503)

    # 3. Clean the repository mapping format for the UI
    cleaned_repos = []
    for repo in repositories_data:
        cleaned_repos.append({
            "id": repo.get("id"),
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "is_private": repo.get("private"),
        })

    # 4. Return pure JSON data directly back to React
    return JsonResponse({
        "total_repos_found": len(cleaned_repos),
        "repositories": cleaned_repos
    })


class CreateUserSelectedRepos(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # 1. Capture payload data array and workspace tracking context headers
        repo_list = request.data.get('repositories', []) # Expects an array list of dicts
        workspace_id = request.data.get('workspace_id')

        if not repo_list or not isinstance(repo_list, list):
            return Response(
                {"error": "Malformed payload structure. 'repositories' must be a non-empty array list."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 2. Securely isolate the target workspace profile layout context
            workspace = Workspace.objects.get(id=workspace_id, owner=request.user)
        except Workspace.DoesNotExist:
            return Response(
                {"error": f"Workspace context matching ID '{workspace_id}' not found or unauthorized."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Mass validate the entire payload matrix using our serializer mapping wrapper
        serializer = GitHubRepositorySerializer(data=repo_list, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # 4. 🏎️ THE ULTIMATE PERFORMANCE STEP: In-Memory Instance Compiling
        # We build the raw Python model objects in local worker memory WITHOUT touching the database yet.
        validated_data_list = serializer.validated_data
        
        # Pull existing saved IDs to prevent duplicate database integrity crashes
        incoming_ids = [item['github_id'] for item in validated_data_list]
        existing_ids = set(GitHubRepository.objects.filter(
            github_id__in=incoming_ids
        ).values_list('github_id', flat=True))

        new_repo_instances = []
        for data in validated_data_list:
            # Skip records that are already connected to keep the database stable
            if data['github_id'] in existing_ids:
                continue

            new_repo_instances.append(
                GitHubRepository(
                    workspace=workspace,
                    github_id=data['github_id'],
                    repo_name=data['repo_name'],
                    repo_owner=data['repo_owner'],
                    repo_full_name=data['repo_full_name'],
                    # Optional metadata fields:
                    # collaborators_url=data.get('collaborators_url'),
                    # branches_url=data.get('branches_url'),
                    # contributors_url=data.get('contributors_url')
                )
            )

        # 5. Execute ONE single pinpoint atomic INSERT database trip request statement
        if new_repo_instances:
            GitHubRepository.objects.bulk_create(new_repo_instances)
            print(f"🎉 BULK INSERT SUCCESS: Saved {len(new_repo_instances)} new repositories.")

        return Response(
            {
                "status": "success",
                "message": f"Successfully processed {len(repo_list)} repository records. Connected {len(new_repo_instances)} new pipelines.",
                "saved_count": len(new_repo_instances)
            }, 
            status=status.HTTP_201_CREATED
        )



@csrf_exempt
@require_github_auth  # Secures the endpoint
def receive_ci_results(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    request_id = uuid.uuid4().hex[:8]
    

    # Fallback default tracking fields
    run_id = None
    repository_owner = None
    repo_name = None
    tool_type = "pytest" # Default fallback for the stream chunks
    file_content = ""
    findings = None
    save_to_db = False


    # =========================================================================
    # 🎯 FIX STATE A: PROCESSING PYTHON CHUNKING ENGINE Payloads (JSON or Trace text)
    # =========================================================================
    if request.content_type == 'application/json':
        raw_body_str = request.body.decode('utf-8')
        print(f"Raw JSON body string length: {raw_body_str}")  # Debugging line to check the raw body content size
        
        try:
            # Try to parse it as clean structured stream JSON
            json_data = json.loads(raw_body_str)
            run_id = json_data.get('run_id')
            repository_owner = json_data.get('repo_owner')
            repo_name = json_data.get('repo')
            tool_type = json_data.get('tool', 'pytest')
            
            logs_list = json_data.get('logs', [])
            file_content = "\n".join(logs_list)

            print("")
            print("json content:", file_content)

            
        except json.JSONDecodeError:
            print("⚠️ ALERT: Pytest stream sent raw trace blocks instead of JSON metadata.")
            file_content = raw_body_str
            
            # Since the json parsing failed, dynamically extract tracking fields 
            # straight from the system header variables or text lines using regex matching!
            run_id = request.headers.get('X-GitHub-Run-Id', 'unknown_run')
            
            # Use regex matching to isolate details directly out of the traceback text if needed, 
            # or fallback safely to repo names extracted from the URL context paths
            repository_owner = "unknown" # Temporary fallback target for your current sandboxed repo account
            repo_name = "Economic/Calendar" # Temporary fallback target for your current sandboxed repo name
            tool_type = "pytest"

    # =========================================================================
    # 🎯 FIX STATE B: PROCESSING MULTIPART FORM DATA PAYLOADS (Bandit, Ruff, Odozi)
    # =========================================================================
    else:
        run_id = request.POST.get('run_id')
        repo_name = request.POST.get('repo')
        repository_owner = request.POST.get('repo_owner')
        tool_type = request.POST.get('tool')
        uploaded_file = request.FILES.get('file')
        
        if uploaded_file:
            file_content = uploaded_file.read().decode('utf-8')
    
    
    # Double check parameters before hitting Celery
    if not all([run_id, repo_name, repository_owner, tool_type]) or not file_content:
        print(f"❌ REJECTED: Missing attributes. Run: {run_id}, Repo: {repo_name}, Tool: {tool_type}")
        return JsonResponse({'error': 'Missing required orchestration tracking parameters'}, status=400)

    try:     
        print("PAYLOAD LENGTH:", len(file_content))
        user_id = User.objects.get(username=repository_owner) # Mock user ID for testing; replace with actual user lookup in production
        
        styled_logs = []
        styled_logs.append(f"")
        styled_logs.append(f"┌──────────────────────────────────────────────────────────┐")
        styled_logs.append(f"  ► SYSTEM INGESTION NOTICE: PIPELINE CORE ACTIVE            ")
        styled_logs.append(f"  ► EXECUTING SCAN VECTOR  : [ {tool_type.upper()} ]         ")
        styled_logs.append(f"└──────────────────────────────────────────────────────────┘")
        styled_logs.append(f"")
        
        # Append actual terminal lines
        styled_logs.extend(file_content.splitlines())
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                f"user_anonymous_sandbox",
                {
                    "type": "chat_message",
                    "message": {
                        "stream_type": "live_logs",
                        "tool": tool_type,
                        "run_id": run_id,
                        "data": styled_logs # Safe uniform text lines array
                    }
                }
            )


        print(
            f"\n🔥 WEBHOOK RECEIVED "
            f"id={request_id} "
            f"tool type={tool_type} "
            f"content_type={request.content_type}"
        )
        print("")

        if request.content_type != 'application/json' and request.content_type != "multipart/form-data":
            
            # Use Regex to see if it's an infrastructure/environment issue or code syntax
            if "UndefinedValueError" in file_content or "KeyError" in file_content:
                msg = "Runtime infrastructure configuration error: Missing required environment variables."
                save_to_db = True
            elif "SyntaxError" in file_content:
                msg = "Code execution blocked: Severe Python syntax error detected in repository code."
                save_to_db = True
            elif "psycopg2.OperationalError" in file_content or "SSL connection" in file_content:
                msg = "Database handshake failure: Target environment database rejected connection strings."
                save_to_db = True
            else:
                msg = f"Internal execution failure: The tool container terminated unexpectedly during analysis."
                save_to_db = False
            
            # only save to DB if it's a known actionable error, otherwise skip to avoid noise in the database records.
            if save_to_db:
                findings = {
                    "status": "tool_crash",
                    "variable": "SYSTEM",
                    "message": msg
                }
        # therefore its json or multipart
        else:
            if tool_type != "pytest":
                save_to_db = True
        
        if save_to_db:
            process_scan_payload_task.delay( # type: ignore
                run_id, 
                repository_owner, 
                repo_name, 
                tool_type, 
                file_content,
                save_to_db, #only save findings to DB if it's a known actionable error, otherwise skip to avoid noise in the database records.
                findings
            )

        return JsonResponse({'status': 'queued', 'message': f'{tool_type} data buffered safely'})
        
    except Workspace.DoesNotExist:
        print(f"❌ REJECTED: Workspace '{repository_owner}' does not exist.")
        return JsonResponse({'error': f'Workspace profile {repository_owner} not configured'}, status=404)
    except Exception as e:
        print(f"❌ VIEW ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)




class DummyApp(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    queryset = UserProfileModel.objects.all()



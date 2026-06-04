import json
import uuid

import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.contrib.auth.models import User
from django.conf import settings


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
from rest_framework_simplejwt.tokens import AccessToken

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync





# account_profile/views.py
import json
import secrets
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from odozi.utils.auth import get_client_ip, get_browser_family, invalidate_user_session


# @csrf_exempt
# def dashboard_view(request):
#     github_access_token = request.session.get('github_access_token')
#     github_token = request.COOKIES.get("github_access_token")
#     print("")
#     print("sesssion", github_access_token, "brooo", github_token)
#     print("")
#     return JsonResponse({"github_access_token": github_access_token})



@csrf_exempt
def dashboard_view(request):
    """
    Consolidated Dashboard Gateway: Validates initialization transit tickets OR active sessions,
    implements a high-performance Cache-Aside Redis data pipeline, and securely manages 
    HttpOnly browser tokens.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Must use POST for security verification."}, status=405)

    # 1. RETRIEVE INCOMING IDENTIFICATION CONTAINERS
    ticket_id = request.COOKIES.get("ticket_id")
    stored_jwt_access_token = request.COOKIES.get("jwt_access_token")
    browser_family = get_browser_family(request)

    token_string = None
    username = None
    user_id = None
    github_access_token = None

    # Base tracking template string for Redis keys
    redis_ticket_key = f"redis_auth_ws_transit_ticket:{ticket_id}" if ticket_id else None

    # FIRST LOGIN HANDSHAKE (Transit Ticket Present) 
    if ticket_id:
        print(ticket_id)
        raw_payload = cache.get(redis_ticket_key) if redis_ticket_key else None
        print(f"📡 [DASHBOARD] Transit execution path. Redis Payload resolved: {raw_payload}")

        if not raw_payload:
            return JsonResponse({"error": "Transit ticket expired or already consumed."}, status=403)

        # Dual-lock fingerprint validation check
        if browser_family != raw_payload.get("browser_family"):
            cache.delete(redis_ticket_key)
            return JsonResponse({"error": "Fingerprint validation failed."}, status=403)

        # Destructure and decrypt your signed application JWT access token string
        try:
            jwt_encrypted_access = raw_payload["jwt_access_token"]
            jwt_decrypted_bytes = decrypt_token(jwt_encrypted_access)
            token_string = jwt_decrypted_bytes.decode("utf-8") if isinstance(jwt_decrypted_bytes, bytes) else jwt_decrypted_bytes

            # Parse claims map variables locally
            parsed_jwt = AccessToken(token_string) # type: ignore
            username = parsed_jwt.get("username")
            user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")

            # Extract the raw GitHub developer token string
            github_encrypted_access = raw_payload["github_access_token"]
            github_decrypted_bytes = decrypt_token(github_encrypted_access)
            github_access_token = github_decrypted_bytes.decode("utf-8") if isinstance(github_decrypted_bytes, bytes) else github_decrypted_bytes

            # 🔥 INSTANT BURN RULE: Destroy transit ticket from RAM immediately
            cache.delete(redis_ticket_key)

        except Exception as e:
            if redis_ticket_key:
                cache.delete(redis_ticket_key)
            return JsonResponse({"error": f"Cryptographic parsing failed: {str(e)}"}, status=401)

    # --- PATH B: SUBSEQUENT PAGE REFRESHES (HttpOnly Cookie Token Present) ---
    elif stored_jwt_access_token:
        print("🍪 [DASHBOARD] Recycled cookie execution path. Authenticating via token string payload...")
        try:
            # If your cookie stores raw unencrypted text, read directly; if encrypted, run decrypt_token()
            token_string = stored_jwt_access_token
            
            print("22222",token_string)
            parsed_jwt = AccessToken(token_string) # type: ignore
            print("UPANDA",parsed_jwt)
            username = parsed_jwt.get("username")
            user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")
            print(f"✅ [DASHBOARD] Token authentication successful. User context resolved: {username} (ID: {user_id})")
            
        except Exception as e:
            print(f"💥 [DASHBOARD AUTH FAILURE] SimpleJWT threw an exception: {str(e)}")
            return JsonResponse({"error": f"Session verification expired or invalid: {str(e)}"}, status=401)

    else:
        print("")
        print("NOTING")
        return JsonResponse({"error": "Anonymous context rejected. Missing valid authentication elements."}, status=403)

    if not username or not user_id:
        return JsonResponse({"error": "Failed to map token identities securely."}, status=401)


    details_cache_key = f"user:repos:{user_id}"
    base_details_cache_key = cache.get(details_cache_key)

    if base_details_cache_key:
        cached_repos = base_details_cache_key["cleaned_repos"]
        github_access_token = base_details_cache_key["github_access_token"]
        print(f"⚡ [CACHE HIT] Serving repositories for '{username}' instantly from Redis RAM.")
        # Handle string parsing dependencies if using raw serialization
        cleaned_repos = json.loads(cached_repos) if isinstance(cached_repos, str) else cached_repos
    else:
        print(f"🌐 [CACHE MISS] Querying fresh data arrays from GitHub REST API for user '{username}'...")
        repos_url = f"https://api.github.com/users/{username}/repos"
        headers = {
            "Authorization": f"Bearer {github_access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Django-Application-Gateway" # GitHub drops headers lacking identifiers
        }

        try:
            github_res = requests.get(repos_url, headers=headers, params={"per_page": 100, "sort": "updated"}, timeout=5.0)
            print(f"📊 [GITHUB API] External status responded: {github_res.status_code}")
            repositories_data = github_res.json() if github_res.status_code == 200 else []
        except requests.RequestException as e:
            print(f"❌ [GITHUB API] Error occurred while fetching repositories: {e}")
            repositories_data = []

        # Parse data defensively mapping dict properties safely
        cleaned_repos = [{
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name")
        } for r in repositories_data if isinstance(r, dict)]

        user_details = {
            "cleaned_repos":cleaned_repos,
            "github_access_token":github_access_token
        }

        # Commit cleaned structures to Redis with a highly scalable 1-hour lifecycle TTL (3600s)
        cache.set(details_cache_key, user_details, timeout=3600)
        print(f"💾 [REDIS] Successfully cached repository state array for user '{username}'.")


    response = JsonResponse({
        "repositories": cleaned_repos,
        "my_jwt_access_token": token_string,
        "username": username,
        "user_id": user_id
    }, status=200)

    response.delete_cookie(
        key="ticket_id",
        path="/",
        samesite="None",
    )

    # Renew the long-lived secure HttpOnly session storage identifier
    response.set_cookie(
        key="jwt_access_token",
        value=str(token_string),
        max_age=28800, # 8 Hours matching standard working cycles
        httponly=True,
        secure=True,     # Forces HTTPS requirement blocks
        samesite="None", # Permits local cross-origin development handshakes
        path="/"
    )

    print(f"🚀 [DASHBOARD] Clean execution complete. Returning data payload for: {username}")
    return response



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



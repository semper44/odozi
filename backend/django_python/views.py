import json
import uuid
import secrets
import requests
from itertools import product
from typing import cast, List

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.contrib.auth.models import User
from django.conf import settings
from django.db import transaction

from agents.tasks import process_scan_payload_task
from account_profile.models import GitHubRepository, Workspace, WorkspaceMembership
from .models import UserProfileModel, RepoEnvKey
from odozi.utils.jwt_cookie_auth import HttpOnlyCookieJWTAuthentication
from odozi.utils.crypto import decrypt_token  
from odozi.utils.security import verify_signature
from odozi.utils.github_auth_decorator import require_github_auth
from odozi.utils.auth import get_client_ip, get_browser_family, invalidate_user_session
from .serializer import GitHubRepositorySerializer, UserProfileSerializer

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync






@csrf_exempt
def dashboard_view(request):
    """
    Consolidated Dashboard Gateway: Validates initialization transit tickets OR active sessions,
    implements a high-performance Cache-Aside Redis data pipeline, and securely manages 
    HttpOnly browser tokens.
    """
    print("wahsahala")
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Must use POST for security verification."}, status=405)

    # 1. RETRIEVE INCOMING IDENTIFICATION CONTAINERS
    ticket_id = request.COOKIES.get("ticket_id")
    stored_jwt_access_token = request.COOKIES.get("jwt_access_token")
    browser_family = get_browser_family(request)

    token_string = None
    token_refresh_string = None
    username = None
    user_id = None
    github_access_token = None
    expires_at = None
    github_res_status = None


    # FIRST LOGIN HANDSHAKE (Transit Ticket Present) 
    if ticket_id:
        print(ticket_id)

        # Base tracking template string for Redis keys
        redis_ticket_key = f"redis_auth_ws_transit_ticket:{ticket_id}" if ticket_id else None
        raw_payload = cache.get(redis_ticket_key) if redis_ticket_key else None
        
        print(f"📡 [DASHBOARD] Transit execution path. Redis Payload resolved")
        
        if not raw_payload:
            return JsonResponse({"error": "Transit ticket expired or already consumed."}, status=403)

        print("passed payload check")
        
        # Dual-lock fingerprint validation check
        if browser_family != raw_payload.get("browser_family"):
            cache.delete(redis_ticket_key)
            return JsonResponse({"error": "Fingerprint validation failed."}, status=403)
        print("passed fingerprint check")
        # Destructure and decrypt your signed application JWT access token string
        try:
            jwt_encrypted_access = raw_payload["jwt_access_token"]
            jwt_decrypted_bytes = decrypt_token(jwt_encrypted_access)
            token_string = jwt_decrypted_bytes.decode("utf-8") if isinstance(jwt_decrypted_bytes, bytes) else jwt_decrypted_bytes
            print(1111)
            # Parse claims map variables locally
            parsed_jwt = AccessToken(token_string) # type: ignore
            username = parsed_jwt.get("username")
            user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")
            print(2222)
            # Extract the raw GitHub developer token string
            github_encrypted_access = raw_payload["github_access_token"]
            github_decrypted_bytes = decrypt_token(github_encrypted_access)
            github_access_token = github_decrypted_bytes.decode("utf-8") if isinstance(github_decrypted_bytes, bytes) else github_decrypted_bytes
            print(3333)
            jwt_encrypted_refresh = raw_payload["jwt_refresh_token"]
            jwt_decrypted_bytes = decrypt_token(jwt_encrypted_refresh)
            token_refresh_string = jwt_decrypted_bytes.decode("utf-8") if isinstance(jwt_decrypted_bytes, bytes) else jwt_decrypted_bytes

            expires_at = raw_payload["expires_at"]

            # 🔥 INSTANT BURN RULE: Destroy transit ticket from RAM immediately
            cache.delete(redis_ticket_key)
            print(444)

        except Exception as e:
            print(f"💥 [DASHBOARD AUTH FAILURE] Decryption or parsing error: {str(e)}")
            if redis_ticket_key:
                cache.delete(redis_ticket_key)
            return JsonResponse({"error": f"Cryptographic parsing failed: {str(e)}"}, status=401)

    # --- PATH B: SUBSEQUENT PAGE REFRESHES (HttpOnly Cookie Token Present) ---
    
    elif stored_jwt_access_token and stored_jwt_access_token != None and stored_jwt_access_token != "None":
        print("🍪 [DASHBOARD] Recycled cookie execution path. Authenticating via token string payload...")
        print(stored_jwt_access_token)
        print(stored_jwt_access_token != None)
        print(stored_jwt_access_token != "None")
        try:
            # If your cookie stores raw unencrypted text, read directly; if encrypted, run decrypt_token()
            github_access_token = stored_jwt_access_token.decode("utf-8") if isinstance(stored_jwt_access_token, bytes) else stored_jwt_access_token
            token_refresh_string = request.COOKIES.get("jwt_refresh_token")

            print("22222",stored_jwt_access_token)
            parsed_jwt = AccessToken(stored_jwt_access_token) # type: ignore
            print("UPANDA",parsed_jwt)
            username = parsed_jwt.get("username")
            # token_string = parsed_jwt.get("my_jwt_access_token")
            token_string = stored_jwt_access_token
            user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")
            print(f"✅ [DASHBOARD] Token authentication successful. User context resolved: {username}||{token_string}")

            expires_at = request.COOKIES.get("expires_at")
            
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
    cached_repos = cache.get(details_cache_key)

    if cached_repos:
        print(f"⚡ [CACHE HIT] Serving repositories for '{username}' instantly from Redis RAM.")
        # Handle string parsing dependencies if using raw serialization
        # cleaned_repos = json.loads(cached_repos) if isinstance(cached_repos, str) else cached_repos
        response = JsonResponse(cached_repos, status=200)
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
            github_res_status = github_res.status_code
        except requests.RequestException as e:
            print(f"❌ [GITHUB API] Error occurred while fetching repositories: {e}")
            repositories_data = []


        # Parse data defensively mapping dict properties safely
        cleaned_repos = [{
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name")
        } for r in repositories_data if isinstance(r, dict)]

        try:
            db_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return JsonResponse({"error": "Database sync user mismatch"}, status=401)

        repo_selection_queryset  = GitHubRepository.objects.filter(
            workspace__members__members=db_user,
            workspace__members__is_active=True,  
            is_active=True                      
        ).select_related('workspace')  


        serialized_repo_selection = list(repo_selection_queryset.values(
            'repo_id', 'workspace__name'
        ))

        user_details = {
            "repositories": cleaned_repos,
            "repo_selection":serialized_repo_selection,
            "my_jwt_access_token": token_string,
            "my_jwt_access_refresh": token_refresh_string,
            "github_access_token": github_access_token,
            "username": username,
            "user_id": user_id,
            "expires_at":expires_at
        }

        # Commit cleaned structures to Redis with a highly scalable 1-hour lifecycle TTL (3600s)
        if github_res_status == 200:
            cache.set(details_cache_key, user_details, timeout=3600)
            print(f"💾 [REDIS] Successfully cached repository state array for user '{username}'.")


        response = JsonResponse({
            "repositories": cleaned_repos,
            "repo_selection":serialized_repo_selection,
            "my_jwt_access_token": token_string,
            "my_jwt_access_refresh": token_refresh_string,
            "username": username,
            "user_id": user_id,
            "expires_at":expires_at
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
    response.set_cookie(
        key="jwt_refresh_token",
        value=str(token_refresh_string),
        max_age=28800, # 8 Hours matching standard working cycles
        httponly=True,
        secure=True,     # Forces HTTPS requirement blocks
        samesite="None", # Permits local cross-origin development handshakes
        path="/"
    )

    print(f"🚀 [DASHBOARD] Clean execution complete. Returning data payload for: {username}")
    return response



class CreateWorkspaceView(APIView):
    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        repo_list = request.data.get('repositories', [])
        user = request.user
        # user = User.objects.get(pk = 1)
        print("repos", repo_list)
        new_workspace_name = request.data.get('new_workspace_name') # Can be a string name or None
        print("ewo", new_workspace_name)
        if not repo_list or not isinstance(repo_list, list):
            print("1 error")
            return Response(
                {"error": "Malformed payload structure. 'repositories' must be a non-empty list."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():              
                # --- PATH B: CREATE A NEW WORKSPACE ON THE FLY ---
                print(1111)
                if new_workspace_name and str(new_workspace_name).strip():
                    # Recover installation_id defensively from your user profile model mapping
                    try:
                        
                        profile = UserProfileModel.objects.get(user=user)
                        print(profile.installation_id)
                        # Fallback placeholder if installation_id hasn't been set yet
                        installation_id = getattr(profile, "installation_id", "3463363364") 
                        print(222)
                    except UserProfileModel.DoesNotExist:
                        installation_id = "dynamic_fallback"

                    print("johhrr", new_workspace_name.strip(), user, "ppp")
                    workspace, created = Workspace.objects.get_or_create(
                        name=new_workspace_name.strip(),
                        owner=user,
                        defaults={
                            "github_account_name": user.username,
                        }
                    )
                    print("yoowaaa", created, workspace.name)

                    if created:
                        print("created")
                        WorkspaceMembership.objects.create(role="admin", workspace=workspace, members=user)
                else:
                    print("errorr")
                    return Response(
                        {"error": "Must provide either an existing 'workspace_id' or a 'new_workspace_name'."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # --- VALIDATE & MASS BULK INSERT REPOSITORIES ---
                print(555)
                serializer = GitHubRepositorySerializer(data=repo_list, many=True)
                if not serializer.is_valid():
                    print(serializer.errors)
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                validated_data_list = serializer.validated_data
                print(444, validated_data_list)
                incoming_ids = [item['repo_id'] for item in validated_data_list]
                print(6666, incoming_ids)
                existing_ids = set(GitHubRepository.objects.filter(
                    repo_id__in=incoming_ids
                ).values_list('repo_id', flat=True))

                new_repo_instances = []
                print(5555, existing_ids)
                for data in validated_data_list:
                    if data['repo_id'] in existing_ids:
                        continue

                    new_repo_instances.append(
                        GitHubRepository(
                            workspace=workspace,
                            repo_id=data['repo_id'], # Ensure your model fields map properly
                            repo_name=data['repo_name'],
                            repo_owner=data['repo_owner'],
                            repo_full_name=data['repo_full_name']
                        )
                    )

                if new_repo_instances:
                    GitHubRepository.objects.bulk_create(new_repo_instances)

                # Evict user's repository state array from Redis cache so dashboard re-syncs instantly
                cache.delete(f"user:repos:{request.user.id}")

                return Response({
                    "status": "success",
                    "message": f"Successfully processed {len(repo_list)} repositories.",
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "saved_count": len(new_repo_instances)
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Transaction failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class DeleteUserSelectedRepos(APIView):
    """
    DRF Class-Based View gateway to securely execute database deletion
    queries with strict multi-tenant workspace ownership checks.
    """
    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated] 

    def post(self, request, *args, **kwargs):
                # B. PARSE INPUT PAYLOAD 
        # Support both: {"repo_ids": [123]} (single) or {"repo_ids": [123, 456, 789]} (bulk)
        target_repo_ids = request.data.get("repo_ids")
        
        # Fallback safeguard in case your frontend accidentally sends a single integer instead of an array list
        if isinstance(target_repo_ids, int):
            target_repo_ids = [target_repo_ids]

        if not target_repo_ids or not isinstance(target_repo_ids, list):
            return Response({"error": "Missing or malformed 'repo_ids' array list parameter."}, status=status.HTTP_400_BAD_REQUEST)

        # C. 🔒 HIGH-SPEED SECURE BULK DELETION (SINGLE SQL INNER JOIN OPERATION)
        # Using __in translates to a high-speed SQL 'WHERE repo_id IN (123, 456)' query
        deleted_count, _ = GitHubRepository.objects.filter(
            repo_id__in=target_repo_ids,             # 👈 CHANGED: Handles lists of any size instantly!
            workspace__members__members_id=request.user.pk,  # Strict tenant multi-ownership protection guard
            workspace__members__is_active=True       
        ).delete()

        if deleted_count == 0:
            return Response({"error": "No matching repositories found or access denied."}, status=404)




class CreateRepoEnvKeys(APIView):
    def post(self, request, *args, **kwargs):
        print("request.data", request.data)
        
        # 1. Safely extract values from request
        repositories_data = request.data.get('repositories', [])
        key_names = request.data.get('key_names', [])
        workspace_name = request.data.get('workspace', '').strip()
        selected_repo_ids = request.data.get('selected', []) # List of selected GitHub IDs
        
        user = User.objects.get(pk=1)

        if not key_names or not isinstance(key_names, list):
            return Response({"error": "'key_names' must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 2. Format environment keys cleanly
                cleaned_keys = list(set([str(name).strip().upper() for name in key_names if str(name).strip()]))

                # 3. Fetch or establish the targeted Workspace environment record
                if workspace_name:
                    repo_workspace = Workspace.objects.get(
                        name=workspace_name, 
                        owner=user
                    )
                else:
                    workspace_name = "Default"
                    repo_workspace, _ = Workspace.objects.get_or_create(
                        name="default", 
                        owner=user,
                        defaults={"github_account_name": user.username}
                    )

                # 4. Map ALL incoming repository data objects into an active memory dictionary lookup
                # Structure: { 102938471: { 'repo_name': 'odozi', ... } }
                incoming_repos_map = {int(repo['repo_id']): repo for repo in repositories_data if 'repo_id' in repo}
                print("")
                print("eze yoyo", incoming_repos_map)
                # 5. Look up which of the SELECTED repositories already exist inside our database
                # Crucial step: We convert selected IDs to integers to ensure strict matching
                
                existing_repos = GitHubRepository.objects.filter(
                    repo_id__in=selected_repo_ids,
                    # workspace=repo_workspace
                )
                print("")
                print("cheche", existing_repos)
                # Create a set of IDs that are already present in the database
                existing_repo_ids = set(existing_repos.values_list('repo_id', flat=True))
                print(000)
                existing_repos_list= list(existing_repos)


                # 6. STEP A: Identify and mass-create missing repositories
                repos_to_create = []
                for github_id in selected_repo_ids:
                    # If it's already in the DB, skip it!
                    print("")
                    print("created", github_id, type(github_id))
                    if int(github_id) in existing_repo_ids:
                        continue
                    
                    # Fetch its raw object parameters from our memory dictionary
                    repo_info = incoming_repos_map.get(int(github_id))
                    print("ttttt", repo_info, github_id)
                    if not repo_info:
                        print(5555, repo_info)
                        continue # Skip if selection mismatch happens
                        
                    repos_to_create.append(
                        GitHubRepository(
                            workspace=repo_workspace,
                            repo_id=github_id,
                            repo_name=repo_info.get('repo_name', ''),
                            repo_owner=repo_info.get('repo_owner', ''),
                            repo_full_name=repo_info.get('repo_full_name', f"{repo_info.get('repo_owner')}/{repo_info.get('repo_name')}")
                        )
                    )

                # Execute creation batch for missing repositories
                if repos_to_create:
                    print(2222)
                    # Django returns the newly generated model rows complete with database auto-increment IDs!
                    created_repos = GitHubRepository.objects.bulk_create(repos_to_create)
                    # Merge our newly created records with our existing records list
                    all_active_repos = existing_repos_list + list(created_repos)
                    print("opppss,", all_active_repos, "oburu", "existing_repos_list", "ogaa", list(created_repos))
                else:
                    all_active_repos = list(existing_repos)
                    print("opppss2222,22", all_active_repos)

                # 7. STEP B: Pull existing environment keys for these repositories to prevent unique crashes
                print(3333)

                # 1. Pull existing environment keys using an explicit list of records
                # values_list('repo_id', 'key_name') yields integers for primary keys: [(4, 'BHADGHAFDJ')]
                existing_env_tuples = RepoEnvKey.objects.filter(
                    repo__in=all_active_repos,
                    key_name__in=cleaned_keys
                ).values_list('repo_id', 'key_name')

                print(cleaned_keys, "7777",all_active_repos)
                
                # Force conversion to integers to guarantee accurate lookups
                existing_env_set = set(existing_env_tuples)
                print("doris", existing_env_set)

                envs_to_create = []
                for repo in all_active_repos:
                    for key in cleaned_keys:
                        # 🌟 FIX: repo.pk is an integer. Ensure your lookup matches the type in existing_env_set!
                        lookup_tuple = (repo.pk, key)  
                        
                        # If this combination checklist match is found, skip it!
                        if lookup_tuple in existing_env_set:
                            print(f"Skipping duplicate: {repo.repo_name} already has {key}")
                            continue
                            
                        print(existing_env_set,"lookup", lookup_tuple)
                        envs_to_create.append(
                            RepoEnvKey(repo=repo, key_name=key)
                        )

                # 2. Fire the bulk creation query safely
                print("env 2create", envs_to_create)
                if envs_to_create:
                    RepoEnvKey.objects.bulk_create(envs_to_create)

                return Response({
                    "status": "success",
                    "message": f"Variables Created for {len(all_active_repos)} in {workspace_name}.",
                    "repositories_created": len(repos_to_create),
                    "environment_keys_created": len(envs_to_create)
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Transaction mapping failure: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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



class AITestSummaryView(APIView):
    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):        
        test_summary = request.data.get("test_summary")
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # prompt = f"""
        #     Task: "{task_title}"
        #     Deadline: "{deadline}"

        #     Return JSON only:
        #     {{
        #     "summary": "short summary",
        #     "improved": "clear actionable task",
        #     "subtasks": ["step 1", "step 2", "step 3"]
        #     }}

        #     RULES:
        #     - MAX 3 subtasks
        #     - No explanations
        #     - No extra text
        #     - Be short and direct
        #     """
        # for attempt in range(3):
        #     try:
        #         response = client.models.generate_content(
        #             model='gemini-2.5-flash', 
        #             contents=prompt
        #         )
        #         raw = response.text
        #         clean = raw.replace("```json", "").replace("```", "").strip()
        #         data = json.loads(clean)
        #         print(response.text, data, "heyyy")

        #         return Response({"data": data})
        #     except errors.ClientError as e:
        #         # Handle quota / rate limit
        #         if "RESOURCE_EXHAUSTED" in str(e):
        #             return Response(
        #                 {"error": "AI limit reached. Please wait a moment."},
        #                 status=429
        #             )

        #         return Response(
        #             {"error": "AI client error", "details": str(e)},
        #             status=500
        #         )

        #     except json.JSONDecodeError:
        #         return Response(
        #             {"error": "Invalid AI response format"},
        #             status=500
        #         )

        #     except Exception as e:
        #         if attempt < 2:
        #             time.sleep(2)
        #             continue

        #         return Response(
        #             {"error": "Unexpected error", "details": str(e)},
        #             status=500
        #         )




class DummyApp(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    queryset = UserProfileModel.objects.all()



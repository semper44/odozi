import os
import boto3
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
from .models import UserProfileModel, RepoEnvKey, WorkflowRunHistory, ChatSession, ChatMessage
from odozi.service import create_workspace_with_repos  
from odozi.utils.jwt_cookie_auth import HttpOnlyCookieJWTAuthentication
from odozi.utils.crypto import decrypt_token  
from odozi.utils.security import verify_signature
from odozi.utils.github_auth_decorator import require_github_auth
from odozi.utils.auth import get_client_ip, get_browser_family, invalidate_user_session
from .serializer import GitHubRepositorySerializer, UserProfileSerializer
from .schema import OrchestratorAction


from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.callbacks import get_openai_callback 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser






@csrf_exempt
@extend_schema(
    summary="Dashboard bootstrap",
    description="Authenticate the browser session, resolve repository data, and return the dashboard payload.",
    responses={
        200: OpenApiResponse(description="Dashboard data returned"),
        401: OpenApiResponse(description="Invalid or expired authentication"),
        403: OpenApiResponse(description="Anonymous or fingerprint validation failed"),
        405: OpenApiResponse(description="Method not allowed"),
    },
)
def dashboard_view(request):
    """Authenticate the dashboard request and return repository data for the signed-in user."""
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
        # print(cached_repos)
        print("idri111111111")
        print("idrisss")
        print(stored_jwt_access_token != None)
        print(stored_jwt_access_token != "None")
        print("")
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
            print(f"✅ [DASHBOARD] Token authentication successful. User context resolved: {username}||{user_id}")
            print("")
            expires_at = request.COOKIES.get("expires_at")
            
        except Exception as e:
            print(f"💥 [DASHBOARD AUTH FAILURE] SimpleJWT threw an exception: {str(e)}")
            return JsonResponse({"error": f"Session verification expired or invalid: {str(e)}"}, status=401)

        print(555555555555)
    else:
        print("")
        print("NOTING")
        return JsonResponse({"error": "Anonymous context rejected. Missing valid authentication elements."}, status=403)

    print("moreeeeeeeeeeeeeeeeeeeeee")
    if not username or not user_id:
        print(99999999999)
        return JsonResponse({"error": "Failed to map token identities securely."}, status=401)


    details_cache_key = f"user:repos:{user_id}"
    cached_repos = cache.get(details_cache_key)

    if cached_repos:
        print("")
        print(cached_repos)
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
        # cleaned_repos = [{
        #     "id": r.get("id"),
        #     "name": r.get("name"),
        #     "full_name": r.get("full_name")
        # } for r in repositories_data if isinstance(r, dict)]
        
        cleaned_repos = []
        # for easy access in tasks.py
        repo_names = []
        for r in repositories_data:
            # 1. Defensive type check
            if not isinstance(r, dict):
                continue
                
            name = r.get("name")
            
            # 2. Append to full structured list
            cleaned_repos.append({
                "id": r.get("id"),
                "name": name,
                "full_name": r.get("full_name")
            })
            
            # 3. Simultaneously append to the flat name list
            if name:
                repo_names.append(name)



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
            "repo_names":repo_names,
            # "my_jwt_access_token": token_string,
            # "my_jwt_access_refresh": token_refresh_string,
            "github_access_token": github_access_token,
            "username": username,
            "user_id": user_id,
            "expires_at":expires_at
        }

        # Commit cleaned structures to Redis with a highly scalable 1-hour lifecycle TTL (3600s)
        if github_res_status == 200:
            cache.set(details_cache_key, user_details, timeout=3600)
            print(f"💾 [REDIS] Successfully cached repository state array for user '{username}'.")

        details_cache_key = f"user:repos:{user_id}"
        cached_repos = cache.get(details_cache_key)
        print("cacheee",  cached_repos)


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

    print("")
    print("------------------------")
    print("dashboard")
    print(str(token_string))
    print("------------------------")
    print("")

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
    """Create a workspace and attach selected repositories to it."""

    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Create workspace",
        description="Create a new workspace and save the selected GitHub repositories under it.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "new_workspace_name": {"type": "string", "example": "My Workspace"},
                    "repositories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "repo_id": {"type": "integer"},
                                "repo_name": {"type": "string"},
                                "repo_owner": {"type": "string"},
                                "repo_full_name": {"type": "string"},
                            },
                        },
                    },
                },
                "required": ["repositories", "new_workspace_name"],
            }
        },
        responses={
            201: OpenApiResponse(description="Workspace created"),
            400: OpenApiResponse(description="Invalid payload"),
            500: OpenApiResponse(description="Transaction failure"),
        },
    )
    
    def post(self, request, *args, **kwargs):
        repo_list = request.data.get('repositories', [])
        new_workspace_name = request.data.get('new_workspace_name')

        try:
            result = create_workspace_with_repos(
                user=request.user,
                workspace_name=new_workspace_name,
                repositories_data=repo_list
            )
            return Response({
                "status": "success",
                "message": f"Successfully processed {result['total_processed']} repositories.",
                "workspace_id": result['workspace_id'],
                "workspace_name": result['workspace_name'],
                "saved_count": result['saved_count']
            }, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Transaction failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeleteUserSelectedRepos(APIView):
    """Delete selected repositories from the authenticated user's accessible workspaces."""
    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Delete selected repositories",
        description="Remove one or more repository records from the authenticated user's workspaces.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "repo_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "example": [101, 102],
                    }
                },
                "required": ["repo_ids"],
            }
        },
        responses={
            200: OpenApiResponse(description="Deletion completed"),
            400: OpenApiResponse(description="Missing or malformed payload"),
            404: OpenApiResponse(description="No matching repositories found"),
        },
    )
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
    """Create environment variable key entries for the selected repositories."""

    @extend_schema(
        summary="Create environment keys",
        description="Register key names for one or more repositories inside a workspace.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "workspace": {"type": "string", "example": "default"},
                    "key_names": {"type": "array", "items": {"type": "string"}},
                    "selected": {"type": "array", "items": {"type": "integer"}},
                    "repositories": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["key_names"],
            }
        },
        responses={
            201: OpenApiResponse(description="Environment keys created or already present"),
            400: OpenApiResponse(description="Invalid payload"),
            500: OpenApiResponse(description="Transaction mapping failure"),
        },
    )
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
                already_exists = False
                for repo in all_active_repos:
                    for key in cleaned_keys:
                        # 🌟 FIX: repo.pk is an integer. Ensure your lookup matches the type in existing_env_set!
                        lookup_tuple = (repo.pk, key)  
                        
                        # If this combination checklist match is found, skip it!
                        if lookup_tuple in existing_env_set:
                            already_exists = True
                            print(f"Skipping duplicate: {repo.repo_name} already has {key}")
                            continue
                            
                        print(existing_env_set,"lookup", lookup_tuple)
                        already_exists = False
                        envs_to_create.append(
                            RepoEnvKey(repo=repo, key_name=key)
                        )

                # 2. Fire the bulk creation query safely
                print("env 2create", already_exists)
                if envs_to_create:
                    RepoEnvKey.objects.bulk_create(envs_to_create)
                else:
                    if already_exists :
                        return Response({
                        "status": "success",
                        "message": "Variables already exists.",
                    }, status=status.HTTP_201_CREATED)

                return Response({
                    "status": "success",
                    "message": f"{len(envs_to_create)} Variables Created for {len(all_active_repos)} repos in {workspace_name} workspace.",
                    "repositories_created": len(repos_to_create),
                    "environment_keys_created": len(envs_to_create)
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Transaction mapping failure: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class CreateUsersRepo(APIView):
    """Create repository records for the selected GitHub repositories in a workspace."""

    @extend_schema(
        summary="Create repositories for workspace",
        description="Save selected GitHub repositories to the requested workspace record.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "workspace": {"type": "string", "example": "default"},
                    "selected": {"type": "array", "items": {"type": "integer"}},
                    "repositories": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["repositories"],
            }
        },
        responses={
            201: OpenApiResponse(description="Repositories created"),
            400: OpenApiResponse(description="Invalid payload"),
            500: OpenApiResponse(description="Transaction mapping failure"),
        },
    )
    def post(self, request, *args, **kwargs):
        print("request.data", request.data)
        
        # 1. Safely extract values from request
        repositories_data = request.data.get('repositories', [])
        workspace_name = request.data.get('workspace', '').strip()
        selected_repo_ids = request.data.get('selected', []) # List of selected GitHub IDs
        
        user = User.objects.get(pk=1)

        if not repositories_data or not isinstance(repositories_data, list):
            return Response({"error": "Please a repo."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
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


                return Response({
                    "status": "success",
                    "message": f"{len(repos_to_create)} Repos Created in {workspace_name} workspace.",
                    "repositories_created": len(repos_to_create),
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": f"Transaction mapping failure: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@csrf_exempt
@require_github_auth  # Secures the endpoint
@extend_schema(
    summary="Receive CI tool results",
    description="Buffer CI test and scan results from tool runners for storage and dashboard streaming.",
    responses={
        200: OpenApiResponse(description="CI payload accepted"),
        400: OpenApiResponse(description="Missing tracking parameters"),
        404: OpenApiResponse(description="Workspace not configured"),
        500: OpenApiResponse(description="Processing failure"),
    },
)
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



class AITestSummaryViews(APIView):
    """Generate an AI-driven orchestration plan from a natural-language request."""

    # authentication_classes = [HttpOnlyCookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def post(self, request):        
        user_input = request.data.get("message", "")
        memory_history = [] # Loaded from your DB as shown earlier

        # 🚀 THE MONITORING WRAPPER
        with get_openai_callback() as cb:
            # Everything executed inside this indentation is tracked!
            result = chain.invoke({
                "chat_history": memory_history,
                "input": user_input
            })
            
            # Extract metrics directly into Python terminal variables
            prompt_tokens = cb.prompt_tokens      # 👈 What your system prompt cost you!
            completion_tokens = cb.completion_tokens  # 👈 What the AI's output generation cost you!
            total_cost = cb.total_cost            # 👈 Exact financial price in USD!

            print("\n============ TOKEN DIAGNOSTICS ============")
            print(f"📥 PROMPT TOKENS (Input Size):  {prompt_tokens}")
            print(f"📤 COMPLETION TOKENS (Output): {completion_tokens}")
            print(f"💰 TOTAL USD RUNTIME COST:     ${total_cost:.5f}")
            print("===========================================\n")
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = '''

        You are the AI Orchestrator Core for Project Odozi, an autonomous agentic CI/CD gateway. Your sole objective is to intercept a user's natural language project description or request, parse their intentions, and convert them into a strict, validated JSON infrastructure configuration schema.
        You have access to a proprietary library of native Python AST Static Analysis Tooling strategies:

        "check_auth"
        - Objective: Finds functions missing a mandatory authentication decorator.
        - Required Params: {"function_prefix": string, "decorator_name": string}

        "check_required_call"
        - Objective: Verifies target functions encapsulate specific architectural expressions (e.g., transaction wrappers).
        - Required Params: {"keyword": string, "required_call": string}

        "check_function_length"
        - Objective: Enforces line boundary thresholds on functions.
        - Required Params: {"keyword": string, "max_lines": integer}

        "check_class_length"
        - Objective: Enforces line boundary limits on target classes inheriting from specified parent modules.
        - Required Params: {"parent_class": string, "max_lines": integer}

        "check_error_handling"
        - Objective: Flags explicit external or risky calls executed outside defensive try/except wrappers.
        - Required Params: {"risky_call": string}

        "check_n_plus_one"
        - Objective: Performance analyzer detecting database interaction statements inside iterative loops.
        - Required Params: {"orm_method": string}

        "check_pii"
        - Objective: Compliance inspector flagging sensitive variable text blocks passed to log targets.
        - Required Params: {"logging_method": string, "sensitive_keywords": string_pipe_separated_like_"email|password|ssn"}

        "check_types"
        - Objective: Pure Python type hint compliance checker. Validates return signatures and parameters.
        - Required Params: {} (Leave params empty)


        ### CRITICAL: INTENT HANDLING REGISTRY

        Evaluate the user's input carefully to match exactly one of the three supported intents below:

        INTENT: "run_static_analysis"
        Trigger this if the user wants to run security checks, type hints, or run static tests against code files.
        Required Structure:
        {
        "intent": "run_static_analysis",
        "repo_meta": {
            "branch": "string (defaults to 'main' if unprovided)",
            "base_branch": "string (defaults to 'main' if unprovided)"
        },
        "environment_variables": {
            "KEY_NAME": "VALUE"
        },
        "active_rules": [
            {
            "strategy": "string_from_registry_exactly",
            "params": { "param_key": "param_value" }
            }
        ]
        }

        INTENT: "create_workspace"
        Trigger this if the user wants to group, add, or register fresh repositories under a brand new workspace container.
        Required Structure:
        {
        "intent": "create_workspace",
        "new_workspace_name": "string (cleaned, stripped name)",
        "repositories": [
            {
            "repo_id": integer,
            "repo_name": "string",
            "repo_owner": "string",
            "repo_full_name": "string (formatted exactly as owner/repo_name)"
            }
        ]
        }

        INTENT: "create_env_keys"
        Trigger this if the user wants to register, attach, or sync environment variable key names across a subset of selected repositories.
        Required Structure:
        {
        "intent": "create_env_keys",
        "workspace": "string (Target workspace name. Defaults to 'default' if unspecified)",
        "key_names": ["string (Force transform all values into upper-case SNAKE_CASE formatting)"],
        "selected": ["string (The specific stringified repo_id values that the user explicitly selected)"],
        "repositories": [
            {
            "repo_id": integer,
            "repo_name": "string",
            "repo_owner": "string",
            "repo_full_name": "string (formatted exactly as owner/repo_name)"
            }
        ]
        }


        ### EXECUTION PIPELINE RULES

        - Evaluate the user's text carefully to extract the target Git configuration, environment variables, or workspace operations.
        - Cross-reference rule instructions to the Tool Registry or Intent Registry. Map them exactly. 
        - If the user mentions general testing, code checking, or type security without specifying tools, auto-map them to relevant validators (e.g., "check types" maps to "check_types").
        - If a requested strategy requires variables that the user did not specify, deduce a smart default based on best engineering practices.
        - Output ONLY a valid JSON object. Do NOT include markdown code blocks, triple backticks (```json), summaries, or conversational pleasantries.

                    
            '''



class AITestSummaryView(APIView):
    """Convert a natural-language request into a structured JSON action plan."""

    # authentication_classes = [HttpOnlyCookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def post(self, request):        
        user_input = request.data.get("message", "")
        memory_history = []  # Loaded from your DB as shown earlier

        # 1. 🎯 DEFINING YOUR SYSTEM PROMPT RIGHT HERE
        # Write your master orchestrator instructions and rule descriptions here.
        system_instruction_text = """
            You are the AI Orchestrator Core for Project Odozi, an autonomous agentic CI/CD gateway. Your sole objective is to intercept a user's natural language project description or request, parse their intentions, and convert them into a strict, validated JSON infrastructure configuration schema.
            You have access to a proprietary library of native Python AST Static Analysis Tooling strategies:

            "check_auth"
            - Objective: Finds functions missing a mandatory authentication decorator.
            - Required Params: {{"function_prefix": string, "decorator_name": string}}

            "check_required_call"
            - Objective: Verifies target functions encapsulate specific architectural expressions (e.g., transaction wrappers).
            - Required Params: {{"keyword": string, "required_call": string}}

            "check_function_length"
            - Objective: Enforces line boundary thresholds on functions.
            - Required Params: {{"keyword": string, "max_lines": integer}}

            "check_class_length"
            - Objective: Enforces line boundary limits on target classes inheriting from specified parent modules.
            - Required Params: {{"parent_class": string, "max_lines": integer}}

            "check_error_handling"
            - Objective: Flags explicit external or risky calls executed outside defensive try/except wrappers.
            - Required Params: {{"risky_call": string}}

            "check_n_plus_one"
            - Objective: Performance analyzer detecting database interaction statements inside iterative loops.
            - Required Params: {{"orm_method": string}}

            "check_pii"
            - Objective: Compliance inspector flagging sensitive variable text blocks passed to log targets.
            - Required Params: {{"logging_method": string, "sensitive_keywords": string_pipe_separated_like_"email|password|ssn"}}

            "check_types"
            - Objective: Pure Python type hint compliance checker. Validates return signatures and parameters.
            - Required Params: {{}} (Leave params empty)


            ### CRITICAL: INTENT HANDLING REGISTRY

            Evaluate the user's input carefully to match exactly one of the three supported intents below:

            INTENT: "run_static_analysis"
            Trigger this if the user wants to run security checks, type hints, or run static tests against code files.
            Required Structure:
            {{
            "intent": "run_static_analysis",
            "repo_meta": {{
                "branch": "string (defaults to 'main' if unprovided)",
                "base_branch": "string (defaults to 'main' if unprovided)"
            }},
            "environment_variables": {{
                "KEY_NAME": "VALUE"
            }},
            "active_rules": [
                {{
                "strategy": "string_from_registry_exactly",
                "params": {{ "param_key": "param_value" }}
                }}
            ]
            }}

            INTENT: "create_workspace"
            Trigger this if the user wants to group, add, or register fresh repositories under a brand new workspace container.
            Required Structure:
            {{
            "intent": "create_workspace",
            "new_workspace_name": "string (cleaned, stripped name)",
            "repositories": [
                {{
                "repo_id": integer,
                "repo_name": "string",
                "repo_owner": "string",
                "repo_full_name": "string (formatted exactly as owner/repo_name)"
                }}
            ]
            }}

            INTENT: "create_env_keys"
            Trigger this if the user wants to register, attach, or sync environment variable key names across a subset of selected repositories.
            Required Structure:
            {{
            "intent": "create_env_keys",
            "workspace": "string (Target workspace name. Defaults to 'default' if unspecified)",
            "key_names": ["string (Force transform all values into upper-case SNAKE_CASE formatting)"],
            "selected": ["string (The specific stringified repo_id values that the user explicitly selected)"],
            "repositories": [
                {{
                "repo_id": integer,
                "repo_name": "string",
                "repo_owner": "string",
                "repo_full_name": "string (formatted exactly as owner/repo_name)"
                }}
            ]
            }}


            ### EXECUTION PIPELINE RULES

            - Evaluate the user's text carefully to extract the target Git configuration, environment variables, or workspace operations.
            - Cross-reference rule instructions to the Tool Registry or Intent Registry. Map them exactly. 
            - If the user mentions general testing, code checking, or type security without specifying tools, auto-map them to relevant validators (e.g., "check types" maps to "check_types").
            - If a requested strategy requires variables that the user did not specify, deduce a smart default based on best engineering practices.
            - Output ONLY a valid JSON object. Do NOT include markdown code blocks, triple backticks (```json), summaries, or conversational pleasantries.
            """

        # Note: We use double curly braces {{ }} above so Python doesn't confuse the JSON format with prompt variables.

        # 2. BIND THE TEXT INTO A LANGCHAIN PROMPT TEMPLATE MATRIX
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_instruction_text),
            MessagesPlaceholder(variable_name="chat_history"), # Tracks conversation state
            ("human", "{input}")                              # Captures the user's immediate message
        ])

        # 3. INITIALIZE THE BASE LLM USING THE GOOGLE DRIVER
        # We pass your API key and toggle temperature down to 0 for strict formatting adherence
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )

        # 4. PIPE THEM TOGETHER TO BUILD THE ACTIVE PIPELINE CHAIN
        # Test A uses StrOutputParser to catch the raw text configuration string
        chain = prompt_template | llm | StrOutputParser()

        # 5. THE RUNTIME MONITORING WRAPPER
        with get_openai_callback() as cb:
            # The execution pipeline triggers right here inside the context block!
            raw_string_response = chain.invoke({
                "chat_history": memory_history,
                "input": user_input
            })
            
            # Extract diagnostics metrics safely from the callback register box
            prompt_tokens = cb.prompt_tokens      
            completion_tokens = cb.completion_tokens  
            total_cost = cb.total_cost            

            print("\n============ TOKEN DIAGNOSTICS ============")
            print(f"📥 PROMPT TOKENS (Input Size):  {prompt_tokens}")
            print(f"📤 COMPLETION TOKENS (Output): {completion_tokens}")
            print(f"💰 TOTAL USD RUNTIME COST:     ${total_cost:.5f}")
            print("===========================================\n")

        # 6. POST-PROCESSING CLEANUP
        # Strip away any markdown formatting elements if the model hallucinated them
        clean_json_string = raw_string_response.replace("```json", "").replace("```", "").strip()
        
        try:
            final_data = json.loads(clean_json_string)
            print(prompt_tokens,"final", final_data)
            print("")
            print(completion_tokens)
            return Response({
                "status": "success",
                "data": final_data,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }
            }, status=status.HTTP_200_OK)
        except json.JSONDecodeError:
            return Response({
                "error": "Failed to parse AI output into valid JSON",
                "raw_output": raw_string_response
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class LogStreamingResultsView(APIView):
    """Buffer live tool logs or archive the final report payload for a workflow run."""

    @extend_schema(
        summary="Stream log results",
        description="Accept live log chunks or a final report upload for a workflow run and archive it.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "repo": {"type": "string"},
                    "logs": {"type": "array", "items": {"type": "string"}},
                    "file": {"type": "string", "format": "binary"},
                },
            }
        },
        responses={
            200: OpenApiResponse(description="Log chunk buffered"),
            201: OpenApiResponse(description="Final log report archived"),
            400: OpenApiResponse(description="Missing run id"),
            500: OpenApiResponse(description="Archiving failed"),
        },
    )
    def post(self, request, *args, **kwargs):
        run_id = request.data.get('run_id')
        repo_full_name = request.data.get('repo')  # e.g., "semper44/odozi"
        incoming_logs = request.data.get('logs', []) # List of strings from YAML
        
        # Check if this is the final structured summary upload block (multipart/form-data)
        is_final_report = 'file' in request.FILES

        if not run_id:
            return Response({"error": "Missing run_id"}, status=status.HTTP_400_BAD_REQUEST)

        # ---------------------------------------------------------------------
        # PHASE 1: HANDLING LIVE CHUNK STREAM SESSIONS
        # ---------------------------------------------------------------------
        if not is_final_report:
            # We append logs into Redis memory cache so they build up fast without hitting DB
            redis_log_key = f"live_logs:{run_id}"
            
            # Fetch existing buffered lines, append new lines, and update Redis cache (valid for 2 hours)
            existing_buffer = cache.get(redis_log_key, [])
            existing_buffer.extend(incoming_logs)
            cache.set(redis_log_key, existing_buffer, timeout=7200)
            
            # Optional: Broadcast `incoming_logs` via WebSockets here for live dashboard visual scrolls!
            return Response({"status": "chunk_buffered"}, status=status.HTTP_200_OK)

        # ---------------------------------------------------------------------
        # PHASE 2: FINAL TERMINAL COMPLETION (Upload completely to R2 Object Storage)
        # ---------------------------------------------------------------------
        # Find or establish metadata database row placeholder
        try:
            repo_instance = GitHubRepository.objects.get(repo_full_name=repo_full_name)
        except GitHubRepository.DoesNotExist:
            return Response({"error": "Repository not tracked"}, status=status.HTTP_400_DEFAULT)

        # Build or get the relational metadata history card
        run_metadata, created = TestWorkflowRun.objects.get_or_create(
            run_id=run_id,
            defaults={
                "repository": repo_instance,
                "status": "success" # Parse status from file if needed
            }
        )

        # Pull the complete combined raw logs from Redis RAM cache
        redis_log_key = f"live_logs:{run_id}"
        full_log_list = cache.get(redis_log_key, [])
        full_log_text = "\n".join(full_log_list)

        # Process the final report.json file payload passed via file upload fields
        report_file = request.FILES['file']
        report_data = json.loads(report_file.read().decode('utf-8'))

        # Update metadata card stats summary metrics directly in PostgreSQL
        run_metadata.total_tests = report_data.get('summary', {}).get('total', 0)
        run_metadata.passed_tests = report_data.get('summary', {}).get('passed', 0)
        run_metadata.failed_tests = report_data.get('summary', {}).get('failed', 0)
        if run_metadata.failed_tests > 0:
            run_metadata.status = "failed"

        # Define destination layout key within Cloudflare R2 bucket storage container
        r2_file_key = f"logs/repo_{repo_instance.id}/run_{run_id}.log"

        try:
            # Upload the heavy combined logs directly into Cloudflare R2
            settings.R2_CLIENT.put_object(
                Bucket=settings.CF_R2_BUCKET_NAME,
                Key=r2_file_key,
                Body=full_log_text,
                ContentType="text/plain"
            )
            
            # Map the clean, remote storage address path key straight into our PostgreSQL row column pointer
            run_metadata.log_storage_path = r2_file_key
            run_metadata.save()

            # Clean up the Redis cache since the run is safely archived
            cache.delete(redis_log_key)

        except Exception as e:
            return Response({"error": f"Cloudflare R2 offloading crashed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "status": "archived_success",
            "message": "Logs offloaded to R2 bucket container seamlessly."
        }, status=status.HTTP_201_CREATED)



class GetWorkflowRunDetailsView(APIView):
    """Return workflow run metadata and signed log download links for a run."""

    @extend_schema(
        summary="Get workflow run details",
        description="Retrieve the recorded workflow run data and log URLs for the specified run id.",
        responses={
            200: OpenApiResponse(description="Workflow run details returned"),
            404: OpenApiResponse(description="Run not found"),
        },
    )
    def get(self, request, run_id):
        try:
            run = WorkflowRunHistory.objects.prefetch_related('steps').get(run_id=run_id)
        except WorkflowRunHistory.DoesNotExist:
            return Response({"error": "Run not found"}, status=404)

        # Initialize standard S3/R2 client interface helper
        r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.CF_R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CF_R2_ACCESS_KEY,
            aws_secret_access_key=settings.CF_R2_SECRET_KEY
        )

        steps_data = []
        for step in run.steps.all():
            presigned_url = None
            if step.log_storage_path:
                # Generate a temporary download link direct to the browser (expires in 15 mins)
                presigned_url = r2_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.CF_R2_BUCKET_NAME, 'Key': step.log_storage_path},
                    ExpiresIn=900
                )

            steps_data.append({
                "tool_name": step.tool_name,
                "status": step.status,
                "summary": step.summary_metrics,
                "log_download_url": presigned_url # 🚀 Direct link straight to cloud storage!
            })

        return Response({
            "run_id": run.run_id,
            "status": run.status,
            "created_at": run.created_at,
            "steps": steps_data
        })


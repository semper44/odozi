import re
import uuid
import json
import hmac
import time
import jwt
import httpx
import hashlib
import requests
import secrets
import datetime
import urllib.parse
from datetime import timedelta
from dateutil.parser import isoparse 

from django.utils import timezone
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from drf_spectacular.utils import extend_schema, OpenApiResponse


from odozi.utils.auth import get_browser_family, get_client_ip
from odozi.utils.crypto import encrypt_token, decrypt_token
from odozi.utils.jwt_cookie_auth import HttpOnlyCookieJWTAuthentication
from odozi.utils.authentication import rotate_github_token
from agents.tasks import run_agentic_pipeline
from .models import UserProfileModel, Workspace, WorkspaceMembership, GitHubRepository, UserLLMConfig
from .serializers import OdoziCustomRefreshToken
from channels.db import database_sync_to_async









def is_input_safe(user_text):
    # Block common shell injection characters
    forbidden_chars = [";", "&&", "||", ">", "<", "|", "$(", "{"]
    if any(char in user_text for char in forbidden_chars):
        return True
    return False



class SaveLLMConfigView(APIView):
    """Persist encrypted LLM provider settings for the application user."""

    # authentication_classes = [HttpOnlyCookieJWTAuthentication]
    # permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Save LLM configuration",
        description="Store or update an LLM provider, model name, and encrypted API key.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "example": "openai"},
                    "model_name": {"type": "string", "example": "gpt-4.1"},
                    "api_key": {"type": "string", "format": "password", "example": "sk-test"},
                },
                "required": ["provider", "model_name", "api_key"],
            }
        },
        responses={
            200: OpenApiResponse(description="Configuration stored successfully"),
            400: OpenApiResponse(description="Incomplete payload"),
            500: OpenApiResponse(description="Storage failure"),
        },
    )
    def post(self, request, *args, **kwargs):
        provider = request.data.get("provider")
        model_name = request.data.get("model_name")
        api_key = request.data.get("api_key")
        user = User.objects.get(pk=1)
        print("sense",request.data)

        # Basic Parameter Boundaries Protection
        if not provider or not model_name or not str(api_key).strip():
            return Response(
                {"error": "Incomplete configuration payload. All fields are mandatory."},
                status=status.HTTP_400_BAD_REQUEST
            )
        print("build-up")
        try:
            with transaction.atomic():
                print("keduuu")
                # Locate an existing record or provision a clean row instance for this user
                config, created = UserLLMConfig.objects.get_or_create(
                    user=user,
                    defaults={
                        "provider": provider.lower().strip(),
                        "model_name": model_name.strip()
                    }
                )
                print(22222)

                # If it already existed, update the non-sensitive parameters
                if not created:
                    config.provider = provider.lower().strip()
                    config.model_name = model_name.strip()

                print(9999888)
                # Encrypt the raw token text using our custom model method!
                config.set_api_key(api_key)
                config.save()

            return Response({
                "status": "success",
                "message": "LLM credentials stored and encrypted successfully."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Internal storage transaction failure: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




def verify_github_signature(request):
    # Get the signature from the header
    signature_header = request.headers.get('X-Hub-Signature-256')
    if not signature_header:
        return False
    
    # Calculate the expected signature using your secret
    # Ensure WEBHOOK_SECRET is in your settings.py
    hash_object = hmac.new(
        settings.WEBHOOK_SECRET.encode('utf-8'),
        msg=request.body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    # Use hmac.compare_digest to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature_header)




@method_decorator(csrf_exempt, name="dispatch")
class GitHubRefreshView(View):
    """Refresh GitHub access tokens using the stored refresh token and cookie state."""

    authentication_classes = [HttpOnlyCookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Refresh GitHub session",
        description="Refresh GitHub credentials from the current browser session and update auth cookies.",
        responses={
            200: OpenApiResponse(description="Token refresh succeeded"),
            400: OpenApiResponse(description="Malformed or missing token information"),
            401: OpenApiResponse(description="Authentication failed"),
            503: OpenApiResponse(description="GitHub request timeout"),
        },
    )
    def post(self, request):

        github_new_tokens = {}

        if request.user.is_authenticated:
            print("shantelllllllll")
            print("")

        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed"}, status=405)

        try:
            print("Refresh token request body:", request.COOKIES)
            refresh_token = request.COOKIES.get("jwt_refresh_token")
            expires_at = request.COOKIES.get("expires_at")
            print("ran through")

        except json.JSONDecodeError:
            return JsonResponse({"error": "Malformed JSON payload"}, status=400)

        refresh = OdoziCustomRefreshToken(refresh_token)
        new_access = str(refresh.access_token)

        print("abeg", refresh)
        print("new_access", new_access)
        print("")

        # ❗ FIX: guard BEFORE parsing
        if expires_at is None:
            print("expires at is:", expires_at)
            return JsonResponse({"error": "Missing expiration timestamp"}, status=400)

        expires_at = isoparse(expires_at)
        elapsed = timezone.now() - expires_at

        # check if its necessary to poll github
        if elapsed is not None and elapsed >= timedelta(hours=7):

            parsed_jwt = AccessToken(new_access)  # type: ignore
            user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")

            print(2222)
            print("into the cache")

            details_cache_key = f"user:repos:{user_id}"
            cached_repos = cache.get(details_cache_key)

            if cached_repos:
                github_refresh_token = cached_repos.get("github_access_token")

                print("cached_repos", cached_repos)

                payload = {
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_APP_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": github_refresh_token,
                }

                headers = {"Accept": "application/json"}

                print("trying github token")

                try:
                    with httpx.Client() as client:
                        res = client.post(
                            "https://github.com",
                            data=payload,
                            headers=headers,
                            timeout=5.0
                        )

                    if res.status_code != 200:
                        return JsonResponse(
                            {"error": "GitHub authorization endpoint rejected request"},
                            status=401
                        )

                    token_data = res.json()

                    if "error" in token_data:
                        return JsonResponse(
                            {"error": token_data.get("error_description")},
                            status=400
                        )

                    github_new_access = token_data.get("access_token")
                    github_new_refresh = token_data.get("refresh_token")
                    expires_in = token_data.get("expires_in", 28800)

                    if request.user.is_authenticated:
                        profile, _ = UserProfileModel.objects.get_or_create(user=request.user)
                        profile.encrypted_access_token = encrypt_token(github_new_access)
                        profile.encrypted_refresh_token = encrypt_token(github_new_refresh)
                        profile.save()

                    github_new_tokens = {
                        "github_access_token": github_new_access,
                        "github_refresh_token": github_new_refresh,
                        "expires_at": expires_in
                    }

                    cached_repos = cache.get(details_cache_key)

                    if cached_repos:
                        cached_repos["github_access_token"] = github_new_access
                        cached_repos["github_refresh_token"] = github_new_refresh
                        cached_repos["expires_at"] = expires_in

                        cache.set(details_cache_key, cached_repos, timeout=3600)

                except httpx.RequestError:
                    return JsonResponse(
                        {"error": "External connection timeout to GitHub gateway"},
                        status=503
                    )

            else:
                print("Cant find github refresh token")

        else:
            print("GitHub expires at is None")

        # ✅ FIX HERE (your crash)
        github_new_tokens["jwt_access_token"] = new_access
        github_new_tokens["jwt_refresh_token"] = str(refresh)

        response = JsonResponse(github_new_tokens)

        print("")
        print("------------------------")
        print("refresh")
        print(str(new_access))
        print("------------------------")
        print("")

        response.set_cookie(
            key="jwt_access_token",
            value=str(new_access),
            max_age=28800,
            httponly=True,
            secure=True,
            samesite="None",
            path="/"
        )

        response.set_cookie(
            key="jwt_refresh_token",
            value=str(refresh),  # <-- FIXED HERE TOO
            max_age=28800,
            httponly=True,
            secure=True,
            samesite="None",
            path="/"
        )

        return response


 


# ✅ FIX A: Restrict the endpoint securely to POST requests only
@csrf_exempt
@require_POST
@extend_schema(
    summary="GitHub webhook receiver",
    description="Accept GitHub webhook events, verify the signature, and queue automation work.",
    responses={
        200: OpenApiResponse(description="Webhook processed or ignored"),
        400: OpenApiResponse(description="Invalid payload"),
        401: OpenApiResponse(description="Missing signature"),
        403: OpenApiResponse(description="Invalid signature"),
    },
)
def github_push_webhook(request):
    
    # A. Fetch the signature header generated by GitHub
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        return JsonResponse({"error": "Mising signature verification header"}, status=401)

    # B. Read your raw request body string bytes
    raw_payload_bytes = request.body

    # C. Calculate your own secure HMAC hash string using your private webhook password
    secret_key_bytes = settings.GITHUB_APP_CLIENT_SECRET.encode('utf-8')
    computed_hash = hmac.new(secret_key_bytes, raw_payload_bytes, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={computed_hash}"

    # D. Compare them securely to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        return JsonResponse({"error": "Invalid signature. Payload source untrusted."}, status=403)


    # 1. Parse the JSON body safely
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload structure")

    # 2. Extract verification headers
    event_type = request.headers.get('X-GitHub-Event')

    if event_type == 'push':
        # For a push, the branch is parsed out of the reference string
        # branch = data.get('ref', '').split('/')[-1]
        print(data, "data")
        repo_url = data.get('repository', {}).get('clone_url')
        default_branch = data.get('repository', {}).get('default_branch', 'master')
        base_branch = default_branch

         # 3. Extract tracking variables from GitHub payload shape
        repo_data = data.get("repository", {})
        repo_name = repo_data.get("name")
        repo_owner = repo_data.get("owner", {}).get("login")
        
        # Extract commit hash and target branch reference string (e.g., "refs/heads/main")
        commit_sha = data.get("after") # The latest commit SHA that was pushed
        ref_string = data.get("ref", "")
        branch = ref_string.split("/")[-1] if ref_string else "main"
        
        # CRITICAL METADATA: This identifies which corporate app installation owns this repository
        installation_id = data.get("installation", {}).get("id")

        if not all([repo_name, repo_owner, commit_sha, installation_id]):
            return JsonResponse({"error": "Missing tracking metrics in payload structure"}, status=400)

        # ⚠️ MOCK MAPPING: In production, your AI agent / DB fetches what the user requested.
        # For this testing kickoff, we pass a default setup array.
        mock_user_rules = [
            {"rule_key": "check_auth", "params": {"function_prefix": "create", "decorator_name": "login_required"}},
            {"rule_key": "check_function_length", "params": {"keyword": "list", "max_lines": 1}}
        ]


#         How to Fix the Pipeline Token Exchange
# To ensure your dynamic code functions exactly like your hardcoded logic, you need to route the event loop exclusively through your GitHub App implementation framework.
# Step 1: Update your Local Development Tunnel Target
# Go to your GitHub Developer Settings -> GitHub Apps.
# Select your App engine profile.
# Scroll to the Webhook URL field configuration block.
# Replace whatever old path is there with your current active localtunnel link: https://loca.lt.
# Step 2: Remove Repository-Level Webhook Links
# Go to your Taskmaster- code repository settings interface, open the Webhooks side tab, and Delete any manually created URL endpoints targeting your local machine. This ensures GitHub sends pure, App-authorized integration events containing genuine validation metadata.
# Step 3: Implement Backend Fail-Safe Fallbacks
# To protect your background Celery tasks from crashing when mixed payloads hit your webserver routing modules, implement a fallback pattern inside your view. If the incoming payload lacks a valid app context wrapper, fallback cleanly to your sandbox developer credential layout:
# python
#         # Extract the real App installation payload signature block
#         installation_id = data.get("installation", {}).get("id")

#         if not installation_id:
            # DEFENSIVE PROGRAMMING: Fallback 


        # 4. HAND OFF TO CELERY: Trigger Phase 2 asynchronously out of sight
        
        run_agentic_pipeline.delay( #type: ignore
            repo_owner=repo_owner,
            repo_name=repo_name,
            default_branch=default_branch,
            repo_data=repo_data,
            commit_sha=commit_sha,
            target_branch=branch,
            ref_string=ref_string,
            installation_id=settings.GITHUB_INSTALLATION_ID,
            user_requested_rules=mock_user_rules
        )

        return JsonResponse({"status": "queued", "commit": commit_sha, "branch": branch})
            
    elif event_type == 'pull_request':
        pr_data = data.get('pull_request', {})
        
        # Target branch for the merge proposal code context
        branch = pr_data.get('head', {}).get('ref')
        repo_url = data.get('repository', {}).get('clone_url')
        
        # ✅ FIX B: Fixed the deep object pathing for Pull Request base branch extraction
        base_branch = pr_data.get('base', {}).get('ref') or data.get('repository', {}).get('default_branch', 'main')
        
    else:
        return JsonResponse({"status": "ignored", "message": f"Event {event_type} not supported"}, status=200)

    # 3. Structural Field Validations
    if not repo_url or not branch:
        return JsonResponse({"error": "Missing repository tracking or reference tracking keys"}, status=400)


    return JsonResponse({"status": "processing", "branch": branch})




@extend_schema(
    summary="GitHub OAuth callback",
    description="Exchange the GitHub OAuth code for an access token and finalize the user session.",
    responses={
        200: OpenApiResponse(description="OAuth flow completed and redirect issued"),
        400: OpenApiResponse(description="Missing or invalid callback data"),
        500: OpenApiResponse(description="Platform misconfiguration"),
    },
)
def github_callback_view(request):
    # 1. Catch the 'code' parameter sent by GitHub in the URL query string
    code = request.GET.get('code')
    if not code:
        return JsonResponse({"error": "No authorization code returned from GitHub"}, status=400)
    installation_id = request.GET.get('installation_id')
    print(request.GET, "jesu")
    # 2. Prepare the background request to trade the code for an Access Token
    # OAuth configuration credentials (keep your Client Secret in your settings.py env)
    client_id = "Iv23liUEbKH7D09scRIZ"
    # Read the variable safely from settings.py. If it's missing, default to an empty string.
    client_secret = getattr(settings, "GITHUB_APP_CLIENT_SECRET", "")
    print("client_secret", client_secret)  # Debugging line to confirm the value is being read correctly

    if not client_secret:
        return JsonResponse({"error": "Platform misconfiguration: GITHUB_APP_CLIENT_SECRET is missing from settings."}, status=500)
        
    token_url = "https://github.com/login/oauth/access_token"
    token_headers = {"Accept": "application/json"}
    token_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": "http://127.0.0.1:8000/account/api/auth/github/callback/"
    }

    # Make the HTTP POST call to GitHub's token engine
    token_response = requests.post(token_url, json=token_payload, headers=token_headers)
    print(token_response.status_code)
    print(token_response.text)
    if token_response.status_code != 200:
        return JsonResponse({"error": "SOMETHING IS WRONG WITH gITHUB"})
    token_data = token_response.json()

    print("token_data", token_data)  # Debugging line to inspect the response from GitHub's token endpoint

    # Extract the token string
    github_access_token = token_data.get("access_token")
    if not github_access_token:
        return JsonResponse({"error": "Failed to exchange code for access token", "details": token_data}, status=400)

    # 3. Use the fresh token to fetch the user's basic profile details
    user_url = "https://api.github.com/user"
    user_headers = {
        "Authorization": f"Bearer {github_access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    user_profile = requests.get(user_url, headers=user_headers).json()
    
    github_username = user_profile.get("login")
    github_email = user_profile.get("email")
    print("user_profile", user_profile)  # Debugging line to inspect the user profile data returned by GitHub

    # 4. Fallback if user's email is private (GitHub returns empty email if hidden)
    if not github_email:
        emails_url = "https://api.github.com/user/emails"
        emails_profile = requests.get(emails_url, headers=user_headers).json()
        # Find the primary verified email address from their list
                # ✅ DEFENSIVE FIX: Ensure emails_profile is an actual list before looping
        if isinstance(emails_profile, list):
            for email_entry in emails_profile:
                # ✅ DEFENSIVE FIX: Verify each item is a dict object, not a plain string error
                if isinstance(email_entry, dict):
                    if email_entry.get("primary") and email_entry.get("verified"):
                        github_email = email_entry.get("email")
                        break
        else:
            print(f"Warning: GitHub emails API did not return a valid list. Payload: {emails_profile}")


    if not github_username:
        return JsonResponse({"error": "Could not extract user details from profile"}, status=400)

    workspace, created = Workspace.objects.get_or_create(
        name = github_username,
            # Django searches the DB using these lookup fields:
        
        # If not found, Django creates it using lookup fields + these defaults:
        defaults={
            "owner": request.user,
            "github_account_name": github_username,
        }
    )
    print("wahala", request.user)
    # workspace= Workspace.objects.create(name=company, owner=request.user, installation_id=installation_id, github_account_name=github_username)
    if created:
        WorkspaceMembership.objects.create(role="admin", workspace=workspace, members=request.user)

    # 5. DB MANAGEMENT: Locate or create the user record in Django

    user, created = User.objects.get_or_create(
        username=github_username,
        defaults={
            "email": github_email or ""
        }
    )
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    access['username'] = str(github_username)
    access['id'] = user.pk
    my_jwt_access_token = str(access)
    my_jwt_refresh_token = str(refresh)

    print("breakpoint", installation_id)

    profile, _ = UserProfileModel.objects.get_or_create(
        user=user,
    )

    print("installation_id", profile)

    raw_access_token = token_data.get("access_token")
    raw_refresh_token = token_data.get("refresh_token")
    expires_in_seconds = int(token_data.get("expires_in", 28800)) # 8 Hours default

     # 2. CAPTURE DUAL-LOCK FINGERPRINT MATRIX Parameters
    browser_family = get_browser_family(request)

    expiration_time = timezone.now() + datetime.timedelta(seconds=expires_in_seconds)
    expires_at_iso = expiration_time.isoformat() # Looks like: "2026-06-02T23:57:00.000Z"

    
    # 1. GENERATE THE SHORT-LIVED 60-SECOND TRANSIT TICKET
    ticket_id = str(uuid.uuid4())
    redis_ticket_key = f"ws_transit_ticket:{ticket_id}"
    if not installation_id:
        profile.installation_id = installation_id
    
    
    profile.encrypted_refresh_token = encrypt_token(raw_refresh_token)
    profile.encrypted_jwt_access_token = encrypt_token(my_jwt_access_token)
    profile.encrypted_jwt_refresh_token = encrypt_token(my_jwt_refresh_token)
    profile.browser_family = browser_family
    profile.expires_at_iso = expires_at_iso
    profile.save()
    
     # Log the user into the active Django session layer
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    print("Tokens encrypted and saved to database successfully.", encrypt_token(my_jwt_access_token))
    # 3. SEAL DATA PACKAGE INSIDE REDIS FOR EXACTLY 60 SECONDS
    if my_jwt_refresh_token and my_jwt_access_token and raw_access_token:
        ticket_payload = {
            "jwt_access_token": encrypt_token(my_jwt_access_token),
            "jwt_refresh_token": encrypt_token(my_jwt_refresh_token),
            "github_access_token": encrypt_token(raw_access_token),
            "browser_family": browser_family,
            "expires_at": expires_at_iso
        }
        cache.set(f"redis_auth_{redis_ticket_key}", ticket_payload, timeout=60)

        print("PPPPPPPPPP")
    else:
        return JsonResponse({"error": "Key Token missing"}, status=500)
    
    details_cache_key = f"user:repos:{user.pk}"

    # This deletes the entire key from Redis RAM instantly
    cache.delete(details_cache_key)
    # 5. SECURE FRAGMENT REDIRECT
    # We use a URL Hash Fragment '#' so network routing nodes/logs can NEVER read it
    react_app_url = "http://localhost:5173/"

    response = HttpResponseRedirect(react_app_url)

    response.set_cookie(
        "ticket_id",
        str(ticket_id),  # Placeholder token value for testing
        max_age=28800,       
        httponly=True,       
        secure=True,         # <--- FORCE TO TRUE! Browser drops SameSite="None" if Secure is False over HTTPS
        samesite="None",     # <--- Keep this on None for cross-origin flights
        path="/"
    )
    response.set_cookie(
        "expires_at",
        str(expires_at_iso),  # Placeholder token value for testing
        max_age=28800,       
        httponly=True,       
        secure=True,         # <--- FORCE TO TRUE! Browser drops SameSite="None" if Secure is False over HTTPS
        samesite="None",     # <--- Keep this on None for cross-origin flights
        path="/"
    )
    # react_app_url = f"https://spicy-flowers-scream.loca.lt/"
    
    return response



@csrf_exempt
@extend_schema(
    summary="Fetch short-lived auth ticket",
    description="Return a one-time transit ticket that the frontend uses to continue authentication.",
    responses={
        200: OpenApiResponse(description="Ticket returned successfully"),
        401: OpenApiResponse(description="Missing ticket cookie"),
        403: OpenApiResponse(description="Ticket expired or missing"),
        409: OpenApiResponse(description="Ticket already served"),
    },
)
def github_ticket(request):
    # This endpoint is used by the frontend websocket bootstrapper to
    # retrieve the short-lived ticket identifier stored in an HttpOnly cookie.
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    ticket_id = request.COOKIES.get('ticket_id')
    if not ticket_id:
        return JsonResponse({'error': 'Missing ticket cookie'}, status=401)

    redis_ticket_key = f"ws_transit_ticket:{ticket_id}"
    cache_key = f"redis_auth_{redis_ticket_key}"
    served_key = f"redis_auth_served_{redis_ticket_key}"

    payload = cache.get(cache_key)
    if not payload:
        return JsonResponse({'error': 'Ticket not found or expired'}, status=403)

    # Prevent serving the same ticket repeatedly
    if cache.get(served_key):
        return JsonResponse({'error': 'Ticket already served'}, status=409)

    # Mark as served for the lifetime of the ticket to avoid duplicate frontend retries
    cache.set(served_key, True, timeout=60)

    # Return the raw ticket string the websocket service expects
    return JsonResponse({'ticket': ticket_id})





# @csrf_exempt
# @require_POST
# def github_installation_webhook(request):
#     """
#     Listens for real-time GitHub App installation events.
#     Creates the Workspace container and links the managing User.
#     """
#     # 1. Parse the incoming webhook body payload safely
#     try:
#         payload = json.loads(request.body)
#     except json.JSONDecodeError:
#         return HttpResponseBadRequest("Malformed JSON payload")

#     # 2. Verify this is explicitly an installation event step
#     event_type = request.headers.get('X-GitHub-Event')
#     if event_type != 'installation':
#         return JsonResponse({"status": "ignored", "message": f"Event {event_type} ignored by this endpoint"}, status=200)

#     action = payload.get("action")  # Can be "created", "deleted", or "suspend"
#     installation_data = payload.get("installation", {})
#     installation_id = installation_data.get("id")
    
#     # Extract the company organization or personal profile username account slot
#     account_data = installation_data.get("account", {})
#     print("account_data", account_data)  # Debugging line to inspect the account data structure returned by GitHub
#     print(" ")
#     print(" ")
#     print(payload,"payload")  # Debugging line to inspect the entire payload structure returned by GitHub
#     github_account_name = account_data.get("login") # e.g., "benmore-tech" or "semper44"

#     if not installation_id or not github_account_name:
#         return JsonResponse({"error": "Missing critical architectural metadata"}, status=400)

#     # =========================================================================
#     # ACTION: CREATED (The User completes Step 2 Installation)
#     # =========================================================================
#     if action == "created":
#         # Look up which Django user profile owns this matching GitHub handle
#         try:
#             target_user = User.objects.get(username=github_account_name)
#         except User.DoesNotExist:
#             # Fallback fallback safety: if testing, map it to the first user or log it
#             target_user = User.objects.first() 
#             if not target_user:
#                 return JsonResponse({"error": "No platform users exist to map this integration"}, status=404)

#         # Create or fetch the core organization workspace block container
#         workspace, ws_created = Workspace.objects.get_or_create(
#             installation_id=installation_id,
#             defaults={"name": github_account_name}
#         )

#         # Build or activate the member permission bridge mapping row
#         membership, mem_created = WorkspaceMembership.objects.get_or_create(
#             user=target_user,
#             workspace=workspace,
#             defaults={"role": "admin", "is_active": True}
#         )
        
#         # If they were previously fired/deleted, restore access cleanly
#         if not membership.is_active:
#             membership.is_active = True
#             membership.save()

#         return JsonResponse({"status": "installed", "workspace_id": workspace.id})

#     # =========================================================================
#     # ACTION: DELETED (The Company Sacks Odozi or Uninstalls it on GitHub)
#     # =========================================================================
#     elif action == "deleted":
#         # Instantly locate and tear down the workspace to protect privacy compliance boundaries
#         try:
#             workspace = Workspace.objects.get(installation_id=installation_id)
#             # This cascades and toggles off memberships automatically via models design rules
#             workspace.delete() 
#             return JsonResponse({"status": "uninstalled_cleanly"})
#         except Workspace.DoesNotExist:
#             return JsonResponse({"status": "already_purged"}, status=200)

#     return JsonResponse({"status": "ignored_action", "action": action})


from agents.orchestrator import start_agentic_workflow
import re
import json
import hmac
import hashlib
import time
import jwt
import requests
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from rest_framework import generics
from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib.auth.models import User



def is_input_safe(user_text):
    # Block common shell injection characters
    forbidden_chars = [";", "&&", "||", ">", "<", "|", "$(", "{"]
    if any(char in user_text for char in forbidden_chars):
        return True
    return False





def get_installation_access_token(installation_id):
    """
    Uses your Private Key to mint a JWT, then exchanges it for a 
    short-lived 1-hour installation access token from GitHub.
    """
    # 1. Prepare the cryptographic JWT claims payload
    issued_at = int(time.time()) - 60  # Account for minor clock drifts (1 min ago)
    expires_at = issued_at + (10 * 60) # JWTs have a maximum lifetime limit of 10 minutes
    
    payload = {
        "iss": settings.GITHUB_APP_ID, # Your App ID
        "iat": issued_at,
        "exp": expires_at,
    }
    
    # 2. Encode and sign the JWT using your multi-line RSA Private Key
    encoded_jwt = jwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")
    
    # 3. Request the temporary installation token from GitHub
    url = f"https://github.com{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {encoded_jwt}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.post(url, headers=headers)
    
    if response.status_code == 201:
        # Success: Returns a dictionary containing your temporary token string
        return response.json().get("token")
    else:
        raise Exception(f"Failed to generate installation token: {response.text}")



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

# ✅ FIX A: Restrict the endpoint securely to POST requests only
@csrf_exempt
@require_POST
def github_webhook(request):
    
    # ⚠️ OPTIONAL SECURITY HOOK: Validate GitHub Webhook Signature Secret
    # signature = request.headers.get('X-Hub-Signature-256')
    # if not signature:
    #     return JsonResponse({"error": "Missing signature verification"}, status=401)
    # (Insert your hmac sha256 validation here using settings.GITHUB_WEBHOOK_SECRET)

    # 1. Parse the JSON body safely
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload structure")

    # 2. Extract verification headers
    event_type = request.headers.get('X-GitHub-Event')

    if event_type == 'push':
        # For a push, the branch is parsed out of the reference string
        branch = data.get('ref', '').split('/')[-1]
        repo_url = data.get('repository', {}).get('clone_url')
        default_branch = data.get('repository', {}).get('default_branch', 'main')
        base_branch = default_branch
        
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

    # 4. Asynchronous Pipeline Triggers
    # Ensure start_agentic_workflow shifts computing workloads immediately off the view loop
    result = start_agentic_workflow(repo_url, branch, base_branch=base_branch)
    
    if result and result.get("status") == "error":
        return JsonResponse(result, status=400) 

    return JsonResponse({"status": "processing", "branch": branch})




def github_callback_view(request):
    # 1. Catch the 'code' parameter sent by GitHub in the URL query string
    code = request.GET.get('code')
    if not code:
        return JsonResponse({"error": "No authorization code returned from GitHub"}, status=400)
    print("code", code)
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
        "redirect_uri": "http://127.0.0.1:8000/api/auth/github/callback/"
    }

    # Make the HTTP POST call to GitHub's token engine
    token_response = requests.post(token_url, json=token_payload, headers=token_headers)
    token_data = token_response.json()

    print("token_data", token_data)  # Debugging line to inspect the response from GitHub's token endpoint

    # Extract the token string
    access_token = token_data.get("access_token")
    if not access_token:
        return JsonResponse({"error": "Failed to exchange code for access token", "details": token_data}, status=400)

    # 3. Use the fresh token to fetch the user's basic profile details
    user_url = "https://api.github.com/user"
    user_headers = {
        "Authorization": f"Bearer {access_token}",
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

    # 5. DB MANAGEMENT: Locate or create the user record in Django
    user, created = User.objects.get_or_create(
        username=github_username,
        defaults={"email": github_email or ""}
    )

    # Log the user into the active Django session layer
    login(request, user)

    # 6. SUCCESS: Send them back to your local frontend interface landing page
    # When using jQuery/Django Templates:
    return redirect("/")
    
    # When using React later, change the line above to redirect to your React app port:
    # return redirect(f"http://localhost:3000/dashboard/?token={access_token}")


# agents/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import WorkspaceMembership

def revoke_developer_access(request, workspace_id, target_user_id):
    # 1. Enforce that only an active Admin of this specific workspace can execute a revoke command
    admin_membership = get_object_or_404(
        WorkspaceMembership, 
        workspace_id=workspace_id, 
        user=request.user, 
        role='admin', 
        is_active=True
    )
    
    # 2. Locate the targeted developer's membership row record
    dev_membership = get_object_or_404(
        WorkspaceMembership, 
        workspace_id=workspace_id, 
        user_id=target_user_id
    )
    
    # 3. Terminate access immediately by flipping the boolean status flag
    dev_membership.is_active = False
    dev_membership.save()
    
    return JsonResponse({"status": "success", "message": "Developer access successfully revoked."})




# Create your views here.

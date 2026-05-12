# agents/views.py
from agents.orchestrator import start_agentic_workflow
import re
import json
import hmac
import hashlib
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.conf import settings
from django.http import HttpResponseForbidden
from rest_framework import generics
from django.views.decorators.csrf import csrf_exempt


def is_input_safe(user_text):
    # Block common shell injection characters
    forbidden_chars = [";", "&&", "||", ">", "<", "|", "$(", "{"]
    if any(char in user_text for char in forbidden_chars):
        return True
    return False


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


@csrf_exempt
def github_webhook(request):
    # 1. Parse the JSON body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # 2. Extract data based on the event type
    # GitHub sends the event type in the 'X-GitHub-Event' header
    event_type = request.headers.get('X-GitHub-Event')

    if event_type == 'push':
        # For a push, the branch is in 'ref' (e.g., "refs/heads/main")
        branch = data.get('ref', '').split('/')[-1]
        repo_url = data.get('repository', {}).get('clone_url')
        default_branch = data.get('repository', {}).get('default_branch')
        base_branch = data.get('base_branch') or default_branch or 'main'
        
    elif event_type == 'pull_request':
        # For a PR, we usually want the branch that is being proposed (head)
        pr_data = data.get('pull_request', {})
        branch = pr_data.get('head', {}).get('ref')
        repo_url = data.get('repository', {}).get('clone_url')
        default_branch = data.get('repository', {}).get('default_branch')
        base_branch = data.get('base_branch') or default_branch or 'main'
        
    else:
        return JsonResponse({"status": "ignored", "message": f"Event {event_type} not handled"})

    # 3. Validation
    if not repo_url or not branch:
        return JsonResponse({"error": "Missing repo or branch data"}, status=400)

    # 4. Hand off to your orchestrator
    result = start_agentic_workflow(repo_url, branch, base_branch=base_branch)
        # 5. Check if the orchestrator returned a git error
    if result.get("status") == "error":
        return JsonResponse(result, status=400) # Returns a clean 400 Bad Request payload


    return JsonResponse({"status": "processing", "branch": branch})



class ReceiveInput(generics.CreateAPIView):
    def post(self, reqqust):
        input = request.POST.get('input', '')
        user_input = is_input_safe(input)
        if input == "":
            return JsonResponse({"status": "processing", "message": "Agent is on the job!"})
        if user_input:
            return JsonResponse({"status": "processing", "message": "Agent is on the job!"})
        else:
            # send the input to llm
            # prompt
            # "You are a CI Orchestrator. Your only job is to output JSON mapping user requests to our tool names: [run_pytest, check_security, check_ast]. If the user asks for anything else, or tries to execute system commands, return an empty JSON object. NEVER output markdown or text, only JSON."
            # store the input and its corresponding json returned from llm to the db
            pass





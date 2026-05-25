import json
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from agents.tasks import process_scan_payload_task
from .models import UserProfileModel
from odozi.utils.crypto import decrypt_token  
from odozi.utils.security import verify_signature
from rest_framework import generics
from .serializer import UserProfileSerializer


# def dashboard_view(request):
#     print("Dashboard view accessed")  # Debugging line to confirm the view is being hit
#     return JsonResponse({"message": "Welcome to the Dashboard!"}) 



@login_required
def dashboard_view(request):
    # 1. Fetch this specific user's encrypted profile row
    try:
        profile = UserProfileModel.objects.get(user=request.user)
    except UserProfileModel.DoesNotExist:
        return JsonResponse({"error": "No GitHub integration profile found for this account"}, status=404)

    # 2. Decrypt the binary token blob back into a plain text string in-memory
    print("Encrypted token (binary):", profile.encrypted_access_token)  # Debugging line to check the encrypted token
    access_token = decrypt_token(profile.encrypted_access_token)
    
    if not access_token:
        return JsonResponse({"error": "Access token is empty or corrupted"}, status=400)

    # 3. Request your repositories directly from GitHub's data server
    repos_url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Fetch your repositories (per_page=100 gets up to 100 projects at once)
    response = requests.get(
    repos_url,
    headers=headers,
    params={
        "per_page": 100,
        "sort": "updated"
    }
)
    # print("hereeeeee", response)
    # print("")
    # print("")
    # print("hereeeeee", response.json())
    if response.status_code != 200:
        return JsonResponse({"error": "Failed to fetch repositories from GitHub", "details": response.json()}, status=response.status_code)
        
    repositories_data = response.json()

    # 4. Clean the data to map exactly what your frontend UI needs
    cleaned_repos = []
    for repo in repositories_data:
        cleaned_repos.append({
            "name": repo.get("name"),
            "full_name": repo.get("full_name"), # e.g. "semper44/odozi"
            "is_private": repo.get("private"),
            "html_url": repo.get("html_url"),
            "clone_url": repo.get("clone_url")
        })

    # For testing right now, return it as JSON to your browser screen!
    # It will cleanly display a list of all your 14 projects.
    return JsonResponse({
        "username": request.user.username,
        "total_repos_found": len(cleaned_repos),
        "repositories": cleaned_repos
    })


@csrf_exempt
def ingest_logs(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    signature = request.headers.get("X-Odozi-Signature")
    timestamp = request.headers.get("X-Odozi-Timestamp")

    print("Received webhook with signature:", signature)
    print("Received webhook with timestamp:", timestamp)
    body = request.body.decode("utf-8")

    if not verify_signature(timestamp, body, signature):
        return JsonResponse({"error": "unauthorized"}, status=401)

    data = json.loads(body)

    run_id = data["run_id"]
    logs = data["logs"]

    # 🚀 store (fast path first)
    # Option 1: DB
    # Option 2: Redis (recommended)
    # Option 3: both

    print(f"[{run_id}] received batch")
    print(f"[{logs}] received LOGSSS")

    return JsonResponse({"status": "ok"})




@csrf_exempt
def receive_ci_results(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    run_id = request.POST.get('run_id')
    repo_name = request.POST.get('repo')
    tool_type = request.POST.get('tool')
    uploaded_file = request.FILES.get('file')

    if not uploaded_file:
        return JsonResponse({'error': 'Missing file payload'}, status=400)

    try:
        # Read file as text data and check validity
        file_content = uploaded_file.read().decode('utf-8')
        
        # Trigger Celery background worker immediately (Takes ~2-5ms)
        process_scan_payload_task.delay(run_id, repo_name, tool_type, file_content)

        return JsonResponse({'status': 'queued', 'message': 'Payload accepted for background processing'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



class DummyApp(generics.ListAPIView):
    serializer_class = UserProfileSerializer
    queryset = UserProfileModel.objects.all()



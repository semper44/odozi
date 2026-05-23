import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import UserProfileModel
from odozi.utils.crypto import decrypt_token  

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


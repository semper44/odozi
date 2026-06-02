# authentication.py
import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

User = get_user_model()

def rotate_github_token(refresh_token):
    """
    Synchronous background call to GitHub to swap an expired or old
    access token for a fresh token pair.
    """
    payload = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {"Accept": "application/json"}
    
    try:
        with httpx.Client() as client:
            response = client.post(
                "https://github.com",
                data=payload,
                headers=headers,
                timeout=5.0
            )
        if response.status_code != 200:
            return None
            
        data = response.json()
        if "error" in data:
            return None
            
        return data  # Contains: access_token, refresh_token, expires_in...
    except httpx.RequestError:
        return None


@database_sync_to_async
def get_user_from_github_token(access_token):
    """
    Validates the GitHub token against GitHub's profile endpoint
    and resolves/provisions the corresponding local Django user.
    """
    if not access_token:
        return None
        
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        with httpx.Client() as client:
            response = client.get("https://github.com", headers=headers, timeout=5.0)
            
        if response.status_code != 200:
            return None
            
        github_data = response.json()
        github_id = github_data.get("id")
        
        # Core Fast-Path principle: Anchorage on immutable github_id integers
        user, _ = User.objects.get_or_create(
            username=f"gh_{github_id}",
            defaults={"is_active": True}
        )
        return user
    except httpx.RequestError:
        return None

import time
import jwt
import requests

from django.conf import settings

from django.db import transaction
from django.core.cache import cache
from rest_framework.exceptions import ValidationError, PermissionDenied
from account_profile.models import Workspace, WorkspaceMembership, GitHubRepository
from django_python.models import RepoEnvKey
from django_python.serializer import GitHubRepositorySerializer




def is_input_safe(user_text):
    # Block common shell injection characters
    forbidden_chars = [";", "&&", "||", ">", "<", "|", "$(", "{"]
    if any(char in user_text for char in forbidden_chars):
        return True
    return False



def create_workspace_with_repos(user, workspace_name: str, repositories_data: list) -> dict:
    if not workspace_name or not str(workspace_name).strip():
        raise ValidationError("Must provide a workspace name.")

    # 🌟 UI Tracker Lists
    repos_attached = []
    already_existed_in_db = []
    freshly_created_in_db = []

    with transaction.atomic():              
        # 1. Create or fetch the Workspace shell
        workspace, workspace_created = Workspace.objects.get_or_create(
            name=workspace_name.strip(),
            owner=user,
            defaults={"github_account_name": user.username}
        )

        if workspace_created:
            WorkspaceMembership.objects.create(role="admin", workspace=workspace, members=user)

        # 2. Process Repository Payloads
        if repositories_data:
            serializer = GitHubRepositorySerializer(data=repositories_data, many=True)
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

            validated_data_list = serializer.validated_data
            incoming_ids = [item['repo_id'] for item in validated_data_list]
            
            # Map existing repositories by their unique GitHub ID token key
            existing_repos_map = {
                repo.repo_id: repo 
                for repo in GitHubRepository.objects.filter(repo_id__in=incoming_ids)
            }

            for data in validated_data_list:
                r_id = data['repo_id']
                repo_info = {
                    "id": r_id,
                    "name": data['repo_name'],
                    "full_name": data['repo_full_name']
                }
                
                if r_id in existing_repos_map:
                    # Repo exists globally: grab instance and add to existing summary tracking list
                    repo_instance = existing_repos_map[r_id]
                    already_existed_in_db.append(repo_info)
                else:
                    # Fresh Repo: instantiate record on disk and add to created tracking list
                    repo_instance = GitHubRepository.objects.create(
                        repo_id=r_id,
                        repo_name=data['repo_name'],
                        repo_owner=data['repo_owner'],
                        repo_full_name=data['repo_full_name']
                    )
                    freshly_created_in_db.append(repo_info)
                
                repos_attached.append(repo_instance)

            # 3. Bulk attach relationships securely across your ManyToMany bridge canvas table
            if repos_attached:
                workspace.repositories.add(*repos_attached)

        # 🌟 UI RETURN PAYLOAD: Returns a clear split detailing exactly what happened
        return {
            "status": "success",
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "is_newly_created": workspace_created
            },
            "summary": {
                "total_processed": len(repositories_data),
                "total_freshly_created": len(freshly_created_in_db),
                "total_already_existed": len(already_existed_in_db)
            },
            "freshly_created_repositories": freshly_created_in_db,
            "already_existing_repositories": already_existed_in_db
        }



def delete_workspace_with_repos(user, workspace_id: int) -> dict:
    """
    Deletes a specific workspace and completely purges any associated repositories 
    that do not belong to any other workspace in the system.
    """
    try:
        workspace = Workspace.objects.get(pk=workspace_id)
    except Workspace.DoesNotExist:
        raise ValidationError("The requested workspace does not exist.")

    # 🛡️ SECURITY CHECK: Ensure the requesting user actually owns this workspace
    if workspace.owner != user:
        raise PermissionDenied("You do not have permission to delete this workspace.")

    workspace_name = workspace.name
    deleted_repos_info = []

    with transaction.atomic():
        # 1. Gather all repositories currently attached to this workspace
        associated_repositories = list(workspace.repositories.all())

        # 2. Delete the workspace (This cascades and clears WorkspaceMembership automatically)
        workspace.delete()

        # 3. CRITICAL PURGE: Find and destroy orphan repositories
        for repo in associated_repositories:
            # If this repository is not linked to any remaining workspace, delete it globally
            if not repo.workspaces.exists():
                deleted_repos_info.append({
                    "id": repo.repo_id,
                    "name": repo.repo_name,
                    "full_name": repo.repo_full_name,
                    "purged_globally": True
                })
                repo.delete()
            else:
                # The repo is still used elsewhere, so it was only unlinked from this workspace
                deleted_repos_info.append({
                    "id": repo.repo_id,
                    "name": repo.repo_name,
                    "full_name": repo.repo_full_name,
                    "purged_globally": False
                })

        # 4. Evict user's repository state array from Redis cache so dashboard re-syncs instantly
        cache.delete(f"user:repos:{user.id}")

    return {
        "status": "success",
        "message": f"Successfully deleted workspace '{workspace_name}' and evaluated sub-assets.",
        "deleted_workspace_id": workspace_id,
        "deleted_workspace_name": workspace_name,
        "affected_repositories_count": len(deleted_repos_info),
        "repositories_summary": deleted_repos_info
    }



def create_repo_env_keys_service(user, repositories_data: list, key_names: list, workspace_name: str, selected_repo_ids: list) -> dict:
    """
    Business service to register missing selected repositories inside a workspace 
    and bulk-inject environment variable keys defensively without duplicates.
    """
    if not key_names or not isinstance(key_names, list):
        raise ValidationError("'key_names' must be a non-empty list.")

    workspace_name = workspace_name.strip() if workspace_name else "default"

    with transaction.atomic():
        # 1. Clean and deduplicate environmental key names
        cleaned_keys = list(set([str(name).strip().upper() for name in key_names if str(name).strip()]))

        # 2. Fetch or establish the targeted Workspace environment record
        if workspace_name.lower() != "default":
            try:
                repo_workspace = Workspace.objects.get(name=workspace_name, owner=user)
            except Workspace.DoesNotExist:
                raise ValidationError(f"Workspace '{workspace_name}' does not exist for this user.")
        else:
            repo_workspace, _ = Workspace.objects.get_or_create(
                name="default", 
                owner=user,
                defaults={"github_account_name": user.username}
            )

        # 3. Map ALL incoming raw repository objects into an active memory lookup dictionary
        incoming_repos_map = {int(repo['repo_id']): repo for repo in repositories_data if 'repo_id' in repo}
        
        # 4. Find which SELECTED repositories already exist inside our database
        existing_repos = GitHubRepository.objects.filter(repo_id__in=selected_repo_ids)
        existing_repo_ids = set(existing_repos.values_list('repo_id', flat=True))
        existing_repos_list = list(existing_repos)

        # 5. STEP A: Identify and track missing repositories for batch insertion
        repos_to_create = []
        for github_id in selected_repo_ids:
            if int(github_id) in existing_repo_ids:
                continue
            
            repo_info = incoming_repos_map.get(int(github_id))
            if not repo_info:
                continue # Skip if metadata is completely missing from cache
                
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
            created_repos = GitHubRepository.objects.bulk_create(repos_to_create)
            all_active_repos = existing_repos_list + list(created_repos)
        else:
            all_active_repos = existing_repos_list

        # 6. STEP B: Pull existing environment keys for these repositories to prevent unique collisions
        existing_env_tuples = RepoEnvKey.objects.filter(
            repo__in=all_active_repos,
            key_name__in=cleaned_keys
        ).values_list('repo_id', 'key_name')
        
        existing_env_set = set(existing_env_tuples)

        envs_to_create = []
        skipped_duplicates_count = 0

        for repo in all_active_repos:
            for key in cleaned_keys:
                lookup_tuple = (repo.pk, key)  
                
                if lookup_tuple in existing_env_set:
                    skipped_duplicates_count += 1
                    continue
                    
                envs_to_create.append(
                    RepoEnvKey(repo=repo, key_name=key)
                )

        # 7. Execute variable key bulk insertion
        if envs_to_create:
            RepoEnvKey.objects.bulk_create(envs_to_create)
            message = f"Successfully created {len(envs_to_create)} keys for {len(all_active_repos)} repos."
        else:
            message = "All requested variable keys already exist for these repositories."

        return {
            "status": "success",
            "message": message,
            "workspace_name": workspace_name,
            "repositories_created_count": len(repos_to_create),
            "environment_keys_created_count": len(envs_to_create),
            "skipped_duplicates_count": skipped_duplicates_count
        }



def get_installation_access_token(installation_id):
    """
    Uses your Private Key to mint a JWT, then exchanges it for a 
    short-lived 1-hour installation access token from GitHub.
    """
    # 1. Prepare the cryptographic JWT claims payload
    issued_at = int(time.time()) - 60  # Account for minor clock drifts (1 min ago)
    expires_at = issued_at + (10 * 60) # JWTs have a maximum lifetime limit of 10 minutes
    
    payload = {
        "iss": settings.ODOZI_APP_ID,  # Your GitHub App's unique identifier
        "iat": issued_at,
        "exp": expires_at,
    }
    

    # 2. Encode and sign the JWT using your multi-line RSA Private Key
    encoded_jwt = jwt.encode(payload, settings.GITHUB_APP_PRIVATE_KEY, algorithm="RS256")
    
    # 3. Request the temporary installation token from GitHub
    url = (
        f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    )
    headers = {
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",

        }
    
    response = requests.post(url, headers=headers)
    print("Status:", response.status_code)
    print("Response:", response.text)
    
    if response.status_code == 201:
        # Success: Returns a dictionary containing your temporary token string
        return response.json().get("token")
    else:
        raise Exception(f"Failed to generate installation token: {response.text}")





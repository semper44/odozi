import time
import jwt
import requests

from django.conf import settings

from django.db import transaction
from django.core.cache import cache
from django.contrib.auth.models import User
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
    that do not belong to any other workspace AND have no remaining environment variable keys.
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

    print("celebrate")

    with transaction.atomic():
        # 1. Gather all repositories currently attached to this workspace
        associated_repositories = list(workspace.repositories.all())

        # 2. Delete the workspace (This cascades and unlinks the repos from this workspace)
        workspace.delete()

        # 3. 🧹 UPGRADED GARBAGE COLLECTION ENGINE: Evaluate workspace-independent assets
        for repo in associated_repositories:
            
            # Criterion 1: Is this repository linked to any remaining workspace?
            is_linked_to_workspaces = repo.workspaces.exists() if hasattr(repo, 'workspaces') else (repo.workspace is not None)
            
            # Criterion 2: Does this repository have any standalone environment keys still assigned?
            has_isolated_env_keys = RepoEnvKey.objects.filter(repo=repo).exists()

            # 🌟 THE STRICT DOUBLE-LOCK PURGE CHECK: 
            # Only wipe the repo from disk if it's completely unassociated with both structures!
            if not is_linked_to_workspaces and not has_isolated_env_keys:
                deleted_repos_info.append({
                    "id": repo.repo_id,
                    "name": repo.repo_name,
                    "full_name": repo.repo_full_name,
                    "purged_globally": True,
                    "reason": "Orphaned from all workspaces and has zero remaining environment keys."
                })
                repo.delete() # 🔥 Physically erased from the database
            else:
                # The repo is preserved because it still has an active workspace link or variable dependency
                preservation_reason = []
                if is_linked_to_workspaces: preservation_reason.append("Linked to another workspace")
                if has_isolated_env_keys: preservation_reason.append("Retains isolated environment keys")
                
                deleted_repos_info.append({
                    "id": repo.repo_id,
                    "name": repo.repo_name,
                    "full_name": repo.repo_full_name,
                    "purged_globally": False,
                    "reason": "Preserved. " + " & ".join(preservation_reason)
                })
        print("ada")
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



def create_repo_env_keys_service(user, repositories_data: list, key_names: list, workspace_name: str, selected_repo_ids: list = None) -> dict:
    """
    Polymorphic business service to bulk-inject environment variables either:
    1. Globally to a complete Workspace (if selected_repo_ids is empty/omitted).
    2. Explicitly to specific Repositories inside that workspace (if selected_repo_ids is provided).
    """
    if not key_names or not isinstance(key_names, list):
        raise ValidationError("'key_names' must be a non-empty list.")

    workspace_name = workspace_name.strip() if workspace_name else "default"
    selected_repo_ids = selected_repo_ids or []

    print(selected_repo_ids, "ronus", workspace_name)

    with transaction.atomic():
        # 1. Clean and uppercase key names to enforce case sanity
        cleaned_keys = list(set([str(name).strip().upper() for name in key_names if str(name).strip()]))

        # 2. Securely resolve the Workspace context
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
        print(selected_repo_ids, "power", repo_workspace)
        envs_to_create = []
        skipped_duplicates_count = 0

        # =====================================================================
        # 📂 CASE A: SCOPING WORKSPACE-WIDE REUSABLE VARIABLES (selected_repo_ids is empty)
        # =====================================================================
        if not selected_repo_ids:
            print("italy")
            # Check existing workspace keys to prevent database constraint failures
            existing_workspace_keys = set(RepoEnvKey.objects.filter(
                workspace=repo_workspace,
                key_name__in=cleaned_keys
            ).values_list('key_name', flat=True))

            print("igbo")

            for key in cleaned_keys:
                if key in existing_workspace_keys:
                    skipped_duplicates_count += 1
                    print("skipping")
                    continue
                
                envs_to_create.append(
                    RepoEnvKey(workspace=repo_workspace, repo=None, key_name=key)
                )
            print("okelezu", envs_to_create)
            if envs_to_create:
                RepoEnvKey.objects.bulk_create(envs_to_create)
                message = f"Successfully injected {len(envs_to_create)} reusable keys into workspace '{workspace_name}'."
            else:
                message = f"All requested keys already exist globally inside workspace '{workspace_name}'."

            return {
                "status": "success",
                "scope": "workspace",
                "message": message,
                "workspace_name": workspace_name,
                "repositories_processed": 0,
                "environment_keys_created_count": len(envs_to_create),
                "skipped_duplicates_count": skipped_duplicates_count
            }

        # =====================================================================
        # 💻 CASE B: SCOPING ISOLATED REPOSITORY VARIABLES (selected_repo_ids has entries)
        # =====================================================================
        else:
            print("selected repooo", selected_repo_ids)
            # Map raw input list items to an in-memory lookup map
            incoming_repos_map = {int(repo['repo_id']): repo for repo in repositories_data if 'repo_id' in repo}
            
            # Identify missing metadata records on the fly
            existing_repos = GitHubRepository.objects.filter(repo_id__in=selected_repo_ids)
            existing_repo_ids = set(existing_repos.values_list('repo_id', flat=True))
            existing_repos_list = list(existing_repos)

            repos_to_create = []
            for github_id in selected_repo_ids:
                if int(github_id) in existing_repo_ids:
                    continue
                
                repo_info = incoming_repos_map.get(int(github_id))
                if not repo_info:
                    continue
                    
                repos_to_create.append(
                    GitHubRepository(
                        workspace=repo_workspace,
                        repo_id=github_id,
                        repo_name=repo_info.get('repo_name', ''),
                        repo_owner=repo_info.get('repo_owner', ''),
                        repo_full_name=repo_info.get('repo_full_name', f"{repo_info.get('repo_owner')}/{repo_info.get('repo_name')}")
                    )
                )

            if repos_to_create:
                created_repos = GitHubRepository.objects.bulk_create(repos_to_create)
                all_active_repos = existing_repos_list + list(created_repos)
            else:
                all_active_repos = existing_repos_list

            # Read existing repo keys to block duplicate insertion actions
            existing_env_set = set(RepoEnvKey.objects.filter(
                repo__in=all_active_repos,
                key_name__in=cleaned_keys
            ).values_list('repo_id', 'key_name'))

            for repo in all_active_repos:
                for key in cleaned_keys:
                    lookup_tuple = (repo.pk, key)  
                    
                    if lookup_tuple in existing_env_set:
                        skipped_duplicates_count += 1
                        continue
                        
                    envs_to_create.append(
                        RepoEnvKey(workspace=None, repo=repo, key_name=key)
                    )

            if envs_to_create:
                RepoEnvKey.objects.bulk_create(envs_to_create)
                message = f"Successfully created {len(envs_to_create)} keys across {len(all_active_repos)} repositories."
            else:
                message = "All requested keys already exist for these specific repositories."

            return {
                "status": "success",
                "scope": "repository",
                "message": message,
                "workspace_name": workspace_name,
                "repositories_processed": len(all_active_repos),
                "environment_keys_created_count": len(envs_to_create),
                "skipped_duplicates_count": skipped_duplicates_count
            }



def delete_repo_env_keys_service(user, key_names: list, delete_which: str, workspace_name: str = None, selected_repo_ids: list = None, selected_repo_names: list = None) -> dict:
    """
    Polymorphic deletion service to bulk-delete environment variables from either:
    1. An entire Workspace globally (if selected_repo_ids is empty/omitted).
    2. Specific Repositories (if selected_repo_ids has entries).
    """
    if not key_names and not workspace_name and selected_repo_ids is None:
        raise ValidationError("Must provide a list of key names to delete.")

    selected_repo_ids = selected_repo_ids or []
    cleaned_keys = list(set([str(name).strip().upper() for name in key_names if str(name).strip()]))
    
    affected_repos = set()
    purged_repos_info = []
    total_deleted_accumulator = 0  # 🌟 NEW MASTER ACCUMULATOR: Protects against naming collisions
    delete_messages = ""
    print("esther", workspace_name, "FRESH-UP", delete_which, "MAMA", selected_repo_ids, "BETTER", cleaned_keys, "HIGHERR")

    with transaction.atomic():
        # =====================================================================
        # 📂 CASE A: DELETING WORKSPACE-WIDE REUSABLE VARIABLES
        # =====================================================================
        if workspace_name and delete_which == "workspace":
            print(77777)
            # 🌟 FIXED: Use owner=user instead of owner=user.username to match model object tracking signatures
            repo_workspace = Workspace.objects.filter(name__icontains=workspace_name.strip(), owner=user,  workspace_env_keys__isnull=False).distinct().first()
            
            if not repo_workspace:
                raise ValidationError(f"No Env found associated with {workspace_name} Workspace.")

            affected_repos = set(repo_workspace.repositories.all())
            print("knack",repo_workspace,"delete_workspace_name")

            delete_query = RepoEnvKey.objects.filter(
                workspace=repo_workspace,
            )
            ws_rows_dropped, _ = delete_query.delete()  # 🌟 Use explicit scope name variables
            total_deleted_accumulator += ws_rows_dropped
            print("delete_query",delete_query,"workspace rows dropped:", ws_rows_dropped)
            delete_messages += f"Deleted all envs in {workspace_name} "

        # =====================================================================
        # 📂 CASE B: DELETING REPOSITORY-SPECIFIC ISOLATED VARIABLES
        # =====================================================================
        if selected_repo_ids and delete_which == "repo":
            print("delete_selected_repo_ids", selected_repo_ids, "seeAM")
            target_repos = GitHubRepository.objects.filter(
                repo_id__in=selected_repo_ids,
            )
            print("target_repos", target_repos, "user", user)
            
            if user:
                target_repos = target_repos.filter(repo_owner=user.username)
                if not target_repos.exists():
                    raise ValidationError(f"No Env found in {selected_repo_names} repositories.")
            else:
                raise ValidationError("User context is required to validate repository ownership.")
            
            affected_repos = set(target_repos)
            print("affected_repos", affected_repos, "cleaned_keys", cleaned_keys)

            # Bulk delete matching keys across these repositories
            delete_query = RepoEnvKey.objects.filter(
                repo__in=target_repos,
            )
            print("tanzania")
            repo_rows_dropped, _ = delete_query.delete()  
            total_deleted_accumulator += repo_rows_dropped
            
            # 🌟 FIXED: Changed 'deleted_count' to 'repo_rows_dropped' to prevent crashes!
            print(delete_query, "yana", repo_rows_dropped, "target_repos", target_repos)
            delete_messages += f"Deleted all envs in {target_repos}. "
        # =====================================================================
        # 📂 CASE C: DELETING GLOBAL VARIABLES BY EXACT KEY NAME
        # =====================================================================
        if key_names and delete_which == "key_names":
            print("delete_key_name")
            delete_query = RepoEnvKey.objects.filter(
                key_name__in=cleaned_keys
            )
            global_rows_dropped, _ = delete_query.delete()
            total_deleted_accumulator += global_rows_dropped
            print(cleaned_keys, "cleaned_keys global rows dropped:", global_rows_dropped)

   
        # =====================================================================
        # 🧹 STEP d: THE SPACE-SAVING ORPHAN REPOSITORY PURGE ENGINE
        # =====================================================================
        print("personal")
        for repo in affected_repos:
            # 🌟 FIX: Query your actual ManyToMany relationship field `workspace` safely using values_list
            workspace_ids = list(repo.workspace.values_list('id', flat=True))
            is_in_any_workspace = repo.workspace.exists()
            
            print(f"Repo: {repo.repo_name} | Linked Workspace IDs: {workspace_ids} | Connected: {is_in_any_workspace}")

            # Safe relational database scanning
            has_remaining_keys = RepoEnvKey.objects.filter(repo=repo).exists() or RepoEnvKey.objects.filter(
                workspace_id__in=workspace_ids
            ).exists()
            
            print(f"Repo: {repo.repo_name} | Has remaining keys: {has_remaining_keys}")

            # Clean purge if completely orphaned
            if not has_remaining_keys and not is_in_any_workspace:
                purged_repos_info.append({
                    "id": repo.repo_id,
                    "name": repo.repo_name,
                    "full_name": repo.repo_full_name
                })
                repo.delete() 
        print("feedd")


        return {
            "status": "success",
            "message": delete_messages,
            # "metrics": {
            #     "variables_deleted": total_deleted_accumulator,  # 🌟 Safely map the safe master variable
            #     "repositories_evaluated": len(affected_repos),
            #     "repositories_purged_globally_count": len(purged_repos_info)
            # },
            # "purged_repositories": purged_repos_info
        }



def unlink_or_purge_single_repo(user, workspace_id: int, repo_id: int) -> dict:
    """
    Removes a single repository from a workspace. If the repo is no longer 
    associated with any other workspace, it is deleted globally to free up space.
    """
    try:
        workspace = Workspace.objects.get(pk=workspace_id, owner=user)
        repo = GitHubRepository.objects.get(repo_id=repo_id)
    except (Workspace.DoesNotExist, GitHubRepository.DoesNotExist):
        raise ValidationError("Workspace or Repository mapping target not found.")

    with transaction.atomic():
        # 1. Break the association link
        workspace.repositories.remove(repo)
        
        purged_globally = False
        # 2. Check if it's an orphan now
        if not repo.workspaces.exists():
            repo.delete() # Purge to free up database rows
            purged_globally = True
            
    return {
        "status": "success",
        "repo_name": repo.repo_name,
        "unlinked_from_workspace": workspace.name,
        "purged_globally": purged_globally
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





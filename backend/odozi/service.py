from django.db import transaction
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from account_profile.models import Workspace, WorkspaceMembership, GitHubRepository
from django_python.serializer import GitHubRepositorySerializer

def create_workspace_with_repos(user, workspace_name: str, repositories_data: list) -> dict:
    if not workspace_name or not str(workspace_name).strip():
        raise ValidationError("Must provide a workspace name.")

    with transaction.atomic():              
        workspace, created = Workspace.objects.get_or_create(
            name=workspace_name.strip(),
            owner=user,
            defaults={"github_account_name": user.username}
        )

        if created:
            WorkspaceMembership.objects.create(role="admin", workspace=workspace, members=user)

        if repositories_data:
            serializer = GitHubRepositorySerializer(data=repositories_data, many=True)
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

            validated_data_list = serializer.validated_data
            incoming_ids = [item['repo_id'] for item in validated_data_list]
            
            # Look up existing repos across the global DB registry instance
            existing_repos = {
                repo.repo_id: repo for repo in GitHubRepository.objects.filter(repo_id__in=incoming_ids)
            }

            repos_to_link = []

            for data in validated_data_list:
                r_id = data['repo_id']
                
                if r_id in existing_repos:
                    repo_instance = existing_repos[r_id]
                else:
                    # If it's a completely fresh repo, create it independently
                    repo_instance = GitHubRepository.objects.create(
                        repo_id=r_id,
                        repo_name=data['repo_name'],
                        repo_owner=data['repo_owner'],
                        repo_full_name=data['repo_full_name']
                    )
                repos_to_link.append(repo_instance)

            # 🚀 Bulk attach relationships safely across your table architecture canvas
            if repos_to_link:
                workspace.repositories.add(*repos_to_link) # type: ignore

        return {
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "total_processed": len(repositories_data)
        }




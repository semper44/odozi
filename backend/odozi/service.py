from django.db import transaction
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from account_profile.models import Workspace, WorkspaceMembership, GitHubRepository
from django_python.serializer import GitHubRepositorySerializer

def create_workspace_with_repos(user, workspace_name: str, repositories_data: list) -> dict:
    """
    Shared logic to create a workspace and bulk insert verified repositories.
    """
    if not workspace_name or not str(workspace_name).strip():
        raise ValidationError("Must provide a workspace name.")

    new_repo_instances = []

    with transaction.atomic():              
        # 1. Create Workspace
        workspace, created = Workspace.objects.get_or_create(
            name=workspace_name.strip(),
            owner=user,
            defaults={"github_account_name": user.username}
        )

        if created:
            WorkspaceMembership.objects.create(role="admin", workspace=workspace, members=user)

        # 2. Validate & Mass Bulk Insert Repositories
        if repositories_data:
            serializer = GitHubRepositorySerializer(data=repositories_data, many=True)
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

            validated_data_list = serializer.validated_data
            incoming_ids = [item['repo_id'] for item in validated_data_list]
            
            existing_ids = set(GitHubRepository.objects.filter(
                repo_id__in=incoming_ids
            ).values_list('repo_id', flat=True))

            for data in validated_data_list:
                if data['repo_id'] in existing_ids:
                    continue

                new_repo_instances.append(
                    GitHubRepository(
                        workspace=workspace,
                        repo_id=data['repo_id'],
                        repo_name=data['repo_name'],
                        repo_owner=data['repo_owner'],
                        repo_full_name=data['repo_full_name']
                    )
                )

            if new_repo_instances:
                GitHubRepository.objects.bulk_create(new_repo_instances)

            # Evict user's repository state array from Redis cache
            cache.delete(f"user:repos:{user.id}")

        return {
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "saved_count": len(new_repo_instances),
            "total_processed": len(repositories_data)
        }

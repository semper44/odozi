# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Workspace, WorkspaceMembership

User = get_user_model()

@receiver(post_save, sender=User)
def create_default_user_workspace(sender, instance, created, **kwargs):
    """
    SENIOR DESIGN PATTERN: Automatically provisions a standard workspace 
    for every new user instantly upon registration.
    """
    if created:
        # 1. Provision a standard workspace seamlessly
        workspace = Workspace.objects.create(
            name=f"{instance.username}-workspace", # Enforces uniqueness
            owner=instance,
            installation_id=0, # Temporary placeholder until GitHub App installation occurs
            github_account_name=instance.username
        )
        
        # 2. Automatically link the creator as an 'admin'
        WorkspaceMembership.objects.create(
            user=instance,
            workspace=workspace,
            role='admin',
            is_active=True
        )

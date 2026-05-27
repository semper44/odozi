from django.db import models
from django.contrib.auth.models import User


# Create your models here.


class UserProfileModel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="user_profile")
    # 2. ENCRYPTED FIELD: Tokens are saved as binary blobs, completely unreadable to hackers
    encrypted_access_token = models.BinaryField(blank=True, null=True)
    encrypted_refresh_token = models.BinaryField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}"


class Workspace(models.Model):
    name = models.CharField(max_length=150, unique=True) # e.g., "Benmore Technologies"
    owner = models.ForeignKey(
        User, related_name="workspace_owner",
        on_delete=models.CASCADE
    )
    # user = models.ForeignKey(UserProfileModel, on_delete=models.CASCADE, related_name="github_integration")
    # 1. This is just a standard ID number, safe to keep as plain text
    installation_id = models.BigIntegerField(unique=True, db_index=True)    
    # Store the name of the company or organization space cleanly
    # e.g., "semper44", "company-a-org", "company-b-org"
    github_account_name = models.CharField(max_length=150)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name



class GitHubRepository(models.Model):
    """
    Represents an actual code repository.
    """
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name="repositories",
        db_index=True
    )
    
    repo_name = models.CharField(max_length=255, db_index=True)        # e.g., "Taskmaster"
    repo_owner = models.CharField(max_length=255, db_index=True)       # e.g., "OdoziEngine"
    repo_id = models.BigIntegerField(unique=True, db_index=True)
    
    # Pre-calculated full slug field for ultra-fast database lookups
    # Indexed to guarantee lightning-fast performance for your curl webhooks
    repo_full_name = models.CharField(max_length=255, unique=True, db_index=True) # e.g., "OdoziEngine/Taskmaster"
    
    # Settings for your app orchestrator
    is_active = models.BooleanField(default=True, db_index=True)
    default_branch = models.CharField(max_length=100, default="main")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GitHub Repository"
        verbose_name_plural = "GitHub Repositories"
        ordering = ['-updated_at']

    def __str__(self):
        return self.repo_full_name

    def save(self, *args, **kwargs):
        # Automatically enforce the standard slug layout format on save
        self.repo_full_name = f"{self.repo_owner}/{self.repo_name}"
        super().save(*args, **kwargs)




# Governance levels: Admin (can invite/revoke), Developer (can only view logs)
ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('developer', 'Developer'),
]

class WorkspaceMembership(models.Model):
    """
    The secure access control bridge. Dictates exactly which developers 
    are authorized to step inside a company's workspace.
    """
    members = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='developer')  
    # Simple status flag to support instant firing/re-hiring lifecycles
    is_active = models.BooleanField(default=True) 
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Enforces that a single user cannot have multiple duplicate membership records in one company
        unique_together = ('members', 'workspace')

    def __str__(self):
        return f"{self.members.username} in {self.workspace.name} ({self.role})"


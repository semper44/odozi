from django.db import models, transaction
from account_profile.models import GitHubRepository, UserProfileModel, Workspace
from django.contrib.auth.models import User


class UserInputModel(models.Model):
    user = models.ForeignKey(UserProfileModel, on_delete=models.CASCADE, related_name="user_input_profile")
    user_input = models.TextField()
    llm_response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


# class UserHistory(models.Model):
#     user = models.OneToOneField(UserProfileModel, on_delete=models.CASCADE, related_name="user_input_profile")
#     llm_response = models.JSONField()
#     created_at = models.DateTimeField(auto_now_add=True)



class RepoEnvKey(models.Model):
    """
    Tracks only the NAMES of the environment variables a user requires.
    We NEVER store the actual secret values on our database for maximum security.
    """
    repo = models.ForeignKey(GitHubRepository, on_delete=models.CASCADE, related_name="repo_env_keys")
    key_name = models.CharField(max_length=255) # e.g., "DJANGO_SECRET_KEY", "STRIPE_API_KEY"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('repo', 'key_name')

    def __str__(self):
        return f"{self.repo} requires {self.key_name}"



class RepositoryScan(models.Model):
    TOOL_CHOICES = [
        ('pytest', 'Pytest'),
        ('ruff', 'Ruff'),
        ('bandit', 'Bandit'),
        ('odozi_visitors', 'Odozi AST Engine'),
    ]
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="repo_workspace")
    run_id = models.CharField(max_length=100)
    repo = models.CharField(max_length=255)
    tool = models.CharField(max_length=50, choices=TOOL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='passed')
    
    # Pre-calculated summary counters 
    total_issues = models.IntegerField(default=0)
    high_severity_count = models.IntegerField(default=0)
    lines_of_code = models.IntegerField(default=0)
    
    # UI-ready lists and raw data
    structured_findings = models.JSONField(default=list) 
    raw_payload = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Repository Scan"
        verbose_name_plural = "Repository Scans"
        ordering = ['-created_at']
        
        unique_together = ('run_id', 'tool')

    def __str__(self):
        return f"{self.repo} | {self.tool} | Run: {self.run_id}"


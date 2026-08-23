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
    Supports both workspace-wide reusability and repository-specific isolation.
    """
    # Nullable workspace link: If set, variables apply to ALL repos in this workspace
    workspace = models.ForeignKey(
        Workspace, 
        on_delete=models.CASCADE, 
        related_name="workspace_env_keys",
        blank=True, 
        null=True
    )
    
    # Nullable repository link: If set, variable is isolated to this specific repository
    repo = models.ForeignKey(
        GitHubRepository, 
        on_delete=models.CASCADE, 
        related_name="repo_env_keys",
        blank=True, 
        null=True
    )
    
    key_name = models.CharField(max_length=255) # e.g., "DJANGO_SECRET_KEY"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Constraints: Ensure uniqueness within both individual scopes
        unique_together = [
            ('workspace', 'key_name'),
            ('repo', 'key_name')
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        # Defensive constraint validation: A variable must belong to exactly one scope layer
        if not self.workspace and not self.repo:
            raise ValidationError("An environment variable must be linked to either a Workspace or a Repository.")
        if self.workspace and self.repo:
            raise ValidationError("An environment variable cannot be linked to both a Workspace and a Repository simultaneously. Choose one scope level.")

    def __str__(self):
        scope = f"Workspace '{self.workspace.name}'" if self.workspace else f"Repo '{self.repo.repo_name}'"
        return f"{scope} requires variable: {self.key_name}"




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



class WorkflowRunHistory(models.Model):
    """
    PARENT TABLE: Tracks the global workflow run context.
    Maps to a single GitHub Actions 'run_id'.
    """
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    repository = models.ForeignKey(GitHubRepository, on_delete=models.CASCADE, related_name="workflow_runs")
    run_id = models.BigIntegerField(unique=True, db_index=True) # GitHub's ${{ github.run_id }}
    branch = models.CharField(max_length=255, default="main")
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Workflow Run #{self.run_id} ({self.status})"


class ToolExecutionStep(models.Model):
    """
    CHILD TABLE: Tracks each individual tool executed inside a parent run.
    Example rows:
      - Parent Run #22 running 'pytest' -> status: Success
      - Parent Run #22 running 'ruff'   -> status: Failed
    """
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    workflow_run = models.ForeignKey(WorkflowRunHistory, on_delete=models.CASCADE, related_name="steps")
    tool_name = models.CharField(max_length=50) # e.g., 'pytest', 'ruff', 'bandit'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    
    # 🌟 The unique storage pointer to Cloudflare R2 file containing this tool's raw logs
    # Format: "logs/run_22/pytest.log"
    log_storage_path = models.CharField(max_length=500, blank=True, null=True)
    
    # Summary Metrics (Stored as JSON so it flexes dynamically per tool)
    # Pytest saves: {"passed": 12, "failed": 0}. Ruff saves: {"errors_found": 3}
    summary_metrics = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('workflow_run', 'tool_name') # One entry per tool per run

    def __str__(self):
        return f"{self.workflow_run.run_id} - {self.tool_name} ({self.status})"





class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('ai', 'AI')]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.role

    class Meta:
        ordering = ['created_at']





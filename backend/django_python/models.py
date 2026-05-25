from django.db import models, transaction
from account_profile.models import UserProfileModel, Workspace
from django.contrib.auth.models import User


class UserInputModel(models.Model):
    user = models.ForeignKey(UserProfileModel, on_delete=models.CASCADE, related_name="user_input_profile")
    user_input = models.TextField()
    llm_response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)



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
    run_id = models.CharField(max_length=100, unique=True)
    repo = models.CharField(max_length=255)
    tool = models.CharField(max_length=50, choices=TOOL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='passed')
    
    # Pre-calculated summary counters for ultra-fast frontend rendering
    total_issues = models.IntegerField(default=0)
    high_severity_count = models.IntegerField(default=0)
    lines_of_code = models.IntegerField(default=0)
    
    # Store clean UI-ready lists and raw data
    structured_findings = models.JSONField(default=list) 
    raw_payload = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)


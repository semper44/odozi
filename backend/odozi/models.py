from django.db import models
import uuid

class AuditWorkflow(models.Model):
    """Tracks the master execution run containing multiple test runner tools."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE)
    repository_name = models.CharField(max_length=255)
    branch = models.CharField(max_length=100, default="master")
    commit_sha = models.CharField(max_length=40, blank=True, null=True)
    status = models.CharField(max_length=20, default="queued") # queued, processing, success, failure
    created_at = models.DateTimeField(auto_now_add=True)

class AuditJob(models.Model):
    """Tracks individual tool runners (pytest, bandit, ruff, odozi_ast) inside a workflow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(AuditWorkflow, related_name="jobs", on_delete=models.CASCADE)
    
    # Tool identifier: 'pytest', 'bandit', 'ruff', 'odozi_ast'
    tool_name = models.CharField(max_length=50) 
    status = models.CharField(max_length=20, default="queued")
    execution_time_seconds = models.IntegerField(default=0)
    
    # 🌟 THE SENIOR LINK: Secret path to your Cloudflare R2 bucket blob object
    log_blob_path = models.CharField(max_length=500, blank=True, null=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

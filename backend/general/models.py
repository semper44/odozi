import uuid
from django.db import models
from account_profile.models import Workspace


    
class AuditJob(models.Model):
    """Tracks individual tool runners (pytest, bandit, ruff, odozi_ast) inside a workflow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.CharField(max_length=50, blank=True, null=True) #llm follow_up report
    execution_time_seconds = models.IntegerField(default=0)
    
    # 🌟 THE SENIOR LINK: Secret path to your Cloudflare R2 bucket blob object
    log_blob_path = models.CharField(max_length=500, blank=True, null=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)

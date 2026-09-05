import uuid
from django.db import models
from account_profile.models import Workspace


    
class AuditJob(models.Model):
    """Tracks individual tool runners (pytest, bandit, ruff, odozi_ast) inside a workflow."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.CharField(max_length=50, blank=True, null=True) #llm follow_up report
    execution_time_seconds = models.IntegerField(default=0)
    pipeline_id = models.UUIDField(unique=True, db_index=True)
    log_blob_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to the log blob in cloud storage") 
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AuditJob {self.id}- {self.pipeline_id}"

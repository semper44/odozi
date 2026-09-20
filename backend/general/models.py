import uuid
from django.db import models
from account_profile.models import Workspace


    
class AuditJob(models.Model):
    """Tracks a pipeline summary and its individual tool-result runs."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    history = models.CharField(max_length=500) #user input history
    report = models.CharField(max_length=50, blank=True, null=True) #llm follow_up report
    execution_time_seconds = models.IntegerField(default=0)
    # One pipeline can dispatch any number of tools/runs.
    pipeline_id = models.UUIDField(db_index=True)
    tool_name = models.CharField(max_length=100, blank=True, default="")
    run_id = models.CharField(max_length=100, blank=True, default="")
    log_blob_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to the log blob in cloud storage") 
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Webhook retries update a result instead of duplicating it.
            models.UniqueConstraint(
                fields=["pipeline_id", "tool_name", "run_id"],
                name="unique_auditjob_pipeline_tool_run",
            ),
        ]
        indexes = [models.Index(fields=["pipeline_id", "created_at"])]

    def __str__(self):
        return f"AuditJob {self.id}- {self.pipeline_id} {self.tool_name or 'summary'}"

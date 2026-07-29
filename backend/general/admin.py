from django.contrib import admin
from .models import AuditWorkflow, AuditJob

# Register your models here.
admin.site.register(AuditJob)
admin.site.register(AuditWorkflow)

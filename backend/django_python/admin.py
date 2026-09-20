from django.contrib import admin
from .models import RepositoryScan, RepoEnvKey, ChatSession, ChatMessage

# Register your models here.
admin.site.register(RepositoryScan)
admin.site.register(RepoEnvKey)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)

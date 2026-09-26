from django.contrib import admin
from .models import RepositoryScan, RepoEnvKey, ChatSession,ChatHistory, ChatMessage

# Register your models here.
admin.site.register(RepositoryScan)
admin.site.register(RepoEnvKey)
admin.site.register(ChatSession)
admin.site.register(ChatHistory)
admin.site.register(ChatMessage)

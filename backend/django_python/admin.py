from django.contrib import admin
from .models import RepositoryScan, UserInputModel, RepoEnvKey, ChatSession, ChatMessage

# Register your models here.
admin.site.register(RepositoryScan)
admin.site.register(UserInputModel)
admin.site.register(RepoEnvKey)
admin.site.register(ChatSession)
admin.site.register(ChatMessage)

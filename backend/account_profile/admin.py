from django.contrib import admin
from .models import UserProfileModel, Workspace, WorkspaceMembership, GitHubRepository

# Register your models here.
admin.site.register(UserProfileModel)
admin.site.register(Workspace)
admin.site.register(WorkspaceMembership)
admin.site.register(GitHubRepository)

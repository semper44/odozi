from django.contrib import admin
from .models import UserProfileModel, Workspace, WorkspaceMembership

# Register your models here.
admin.site.register(UserProfileModel)
admin.site.register(Workspace)
admin.site.register(WorkspaceMembership)

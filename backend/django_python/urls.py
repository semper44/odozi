from django.urls import path
from .views import (dashboard_view, CreateRepoEnvKeys,
                    CreateWorkspaceView,DeleteWorkspaceView, receive_ci_results,
                    DeleteRepoEnvKeysView)



urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("results/", receive_ci_results, name="results"),
    path('api/repos/env-keys/create/', CreateRepoEnvKeys.as_view(), name='env-keys-create'),
    path('api/repositories/env-keys/delete/', DeleteRepoEnvKeysView.as_view(), name='delete-repo-env-keys'),
    path('api/workspaces/repos/create/', CreateWorkspaceView.as_view(), name='workspace-create'),
    path('api/workspaces/repos/delete/', DeleteWorkspaceView.as_view(), name='workspace-delete'),

]
from django.urls import path
from .views import (DeleteUserSelectedRepos, dashboard_view, CreateRepoEnvKeys,
                    CreateWorkspaceView, receive_ci_results,
                    CreateUsersRepo)



urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("results/", receive_ci_results, name="results"),
    path('api/repos/create/', CreateUsersRepo.as_view(), name='repo-bulk-create'),
    path('api/workspaces/repos/delete', DeleteUserSelectedRepos.as_view(), name='repo-delete'),
    path('api/repos/env-keys/create/', CreateRepoEnvKeys.as_view(), name='env-keys-create'),
    path('api/workspaces/repos/create/', CreateWorkspaceView.as_view(), name='workspace-create'),

]
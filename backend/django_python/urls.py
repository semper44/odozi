from django.urls import path
from .views import dashboard_view, DummyApp, CreateUserSelectedRepos, receive_ci_results



urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("results/", receive_ci_results, name="results"),
    path("list/", DummyApp.as_view(), name="list_users"),
    path('workspaces/repositories/create', CreateUserSelectedRepos.as_view(), name='repo-bulk-create'),

]
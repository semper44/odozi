from django.urls import path
from .views import dashboard_view, DummyApp, receive_ci_results



urlpatterns = [
    path("", dashboard_view),
    path("results/", receive_ci_results, name="results"),
    path("list/", DummyApp.as_view(), name="list_users"),
]
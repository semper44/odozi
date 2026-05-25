from django.urls import path
from .views import dashboard_view, DummyApp, ingest_logs



urlpatterns = [
    path("", dashboard_view),
    path("results/", ingest_logs, name="results"),
    path("list/", DummyApp.as_view(), name="list_users"),
]
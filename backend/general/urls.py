from django.urls import path
from .views import OptimizedResultsReceiverView, CloudinaryHistoryReportView



urlpatterns = [
    path("results/", OptimizedResultsReceiverView.as_view(), name="results"),
    path("cloudinary-report/<str:pipeline_id>/", CloudinaryHistoryReportView.as_view(), name="cloudinary-report"),

]
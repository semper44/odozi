from django.urls import path
from .views import OptimizedResultsReceiverView,ChatHistoryReportView, CloudinaryHistoryReportView



urlpatterns = [
    path("results/", OptimizedResultsReceiverView.as_view(), name="results"),
    path("cloudinary-report/<str:pipeline_id>/", CloudinaryHistoryReportView.as_view(), name="cloudinary-report"),
    path("api/chat-history/<int:session>/", ChatHistoryReportView.as_view(), name="chat-history"),

]
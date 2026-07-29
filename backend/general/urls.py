from django.urls import path
from .views import OptimizedResultsReceiverView



urlpatterns = [
    path("results/", OptimizedResultsReceiverView.as_view(), name="results"),

]
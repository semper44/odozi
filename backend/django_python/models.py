from django.db import models, transaction
from account_profile.models import UserProfileModel


class UserInputModel(models.Model):
    user = models.ForeignKey(UserProfileModel, on_delete=models.CASCADE, related_name="user_input_profile")
    user_input = models.TextField()
    llm_response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

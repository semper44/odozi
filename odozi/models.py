from django.db import models, transaction

class UserInputModel(models.Model):
    user_input = models.TextField()
    llm_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Input at {self.timestamp}"
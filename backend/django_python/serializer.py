from rest_framework import serializers
from .models import UserInputModel 

class UserInputModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInputModel
        fields = '__all__'

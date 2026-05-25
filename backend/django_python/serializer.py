from rest_framework import serializers
from .models import UserInputModel 
from account_profile.models import UserProfileModel

class UserInputModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInputModel
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfileModel
        fields = '__all__'

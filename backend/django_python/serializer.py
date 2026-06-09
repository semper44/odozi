from rest_framework import serializers
from .models import UserInputModel, GitHubRepository 
from account_profile.models import UserProfileModel

class UserInputModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInputModel
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfileModel
        fields = '__all__'

class GitHubRepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubRepository
        fields = '__all__'
        read_only_fields = ['workspace']

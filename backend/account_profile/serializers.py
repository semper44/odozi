from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

class MyCustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        # 1. Run the default SimpleJWT validation logic
        # This checks if the refresh token cookie string is valid/unexpired
        data = super().validate(attrs)
        
        # 2. Extract the user instance from the validated refresh token payload
        refresh_token_string = attrs["refresh"]
        refresh_token_obj = RefreshToken(refresh_token_string)
        user_id = refresh_token_obj.payload.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            
            # 3. Create a temporary token object to recalculate claims
            # We target SimpleJWT's internal token wrapper tracking dictionary
            new_access_token = refresh_token_obj.access_token
            new_access_token.payload['username'] = str(user.username)
            new_access_token.payload['id'] = int(user.pk) #type: ignore
            
            # 4. Overwrite the default access token string inside the return dictionary data payload
            data['access'] = str(new_access_token)
            
        except User.DoesNotExist:
            pass # Fallback cleanly if user cannot be found mapped to that token scope
            
        return data

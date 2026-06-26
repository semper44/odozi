# account_profile/serializers.py
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

class OdoziCustomRefreshToken(RefreshToken):
    """
    Staff-Level Custom Token Class.
    Ensures custom claims are injected globally whenever an access token 
    is generated or rotated from this refresh token instance.
    """
    @property
    def access_token(self):
        # 1. Generate the baseline standard access token object
        access = super().access_token
        
        # 2. Extract the user identity safely from the current refresh payload
        user_id = self.payload.get("user_id")
        
        if user_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=user_id)
                # 🚀 FORCE claims directly onto the payload before string serialization!
                access["username"] = str(user.username)
                access["id"] = int(user.pk)
            except User.DoesNotExist:
                pass
                
        return access

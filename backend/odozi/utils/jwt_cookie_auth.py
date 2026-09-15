# authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class HttpOnlyCookieJWTAuthentication(JWTAuthentication):
    """
    Custom authentication class that instructs DRF to extract 
    and validate SimpleJWT tokens straight from HttpOnly cookies.
    """
    def authenticate(self, request):
        # 1. Grab the token string from your secure cookie wrapper
        raw_token = request.COOKIES.get("jwt_access_token")
        
        if not raw_token:
            return None # Passes execution to the next auth class or leaves user as Anonymous

        # 2. Validate the token signature using SimpleJWT's native engine
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token) # ✅ Attaches the user directly to request.user!
        except Exception:
            raise AuthenticationFailed("Invalid or expired session cookie.")

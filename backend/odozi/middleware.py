# middleware.py
from typing import Any, Dict
from urllib.parse import parse_qs
from django.core.cache import cache
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from odozi.utils.crypto import decrypt_token


@database_sync_to_async
def get_user_from_db(user_id: Any) -> Any:
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        print(f"🔍 [WS-AUTH] Database lookup successful for User ID {user_id}: {user.username}")
        return user
    except User.DoesNotExist:
        print(f"❌ [WS-AUTH] Database lookup failed. No user found matching ID: {user_id}")
        return AnonymousUser()

class CookieJwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> Any:
        
        # 1. Parse the incoming cookies header string
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("utf-8")
        
        
        # Parse cookies safely into a usable dictionary
        cookies = {}
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                k, v = cookie.strip().split("=", 1)
                cookies[k] = v

        # 2. Extract your secure token cookie name
        # ⚠️ MAKE SURE THIS MATCHES EXACTLY WITH WHAT YOU SET IN YOUR SET_COOKIE FUNCTION!
        
        encrypted_jwt = cookies.get("jwt_access_token") 
        print("ssssssssssssssssssss", encrypted_jwt)
        
        if encrypted_jwt:
            try:
                # 3. Try to decrypt the token
                token_string = encrypted_jwt.decode("utf-8") if isinstance(encrypted_jwt, bytes) else encrypted_jwt
                print("kkkkk", token_string)
                
                # 4. Try to parse token and verify cryptographic signature locally
                parsed_jwt = AccessToken(token_string)  # type: ignore
                print(111111111111)
                user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")
                print(222222222)
                
                # 5. Look up user inside database
                scope["user"] = await get_user_from_db(user_id) # type: ignore
                print(3333333333)
                details_cache_key = f"user:repos:{user_id}"
                print(4444)
                cached_details = cache.get(details_cache_key)
                print(5555, cached_details)
                if cached_details:
                    encrypted_jwt = cached_details["github_access_token"]
                    print(6666)
                    scope["github_token"] = encrypted_jwt
                else:
                    return HttpResponse("Not authorized", status=401)
                print(77777)
                
            except Exception as e:
                print(f"💥 [WS-AUTH] CRITICAL REJECTION: Parsing/Decryption exploded! Error: {str(e)}")
                scope["user"] = AnonymousUser() # type: ignore
                return HttpResponse("Something wrong with authentication, please try again", status=400)
        else:
            print("⚠️ [WS-AUTH] REJECTION: 'my_jwt_access_token' cookie was entirely missing from WebSocket handshake headers.")
            scope["user"] = AnonymousUser() # type: ignore
            return HttpResponse("Not authenticated", status=400)

        print("--- 📡 FORWARDING TO CONSUMER ROUTER ---")
        return await self.inner(scope, receive, send) # type: ignore



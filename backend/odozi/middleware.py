# middleware.py
from typing import Any, Dict
from urllib.parse import parse_qs
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from odozi.utils.crypto import decrypt_token
import time


class RequestDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()

        print(
            f"🚨 REQUEST START: "
            f"{request.method} {request.get_full_path()}"
        )

        try:
            response = self.get_response(request)

            elapsed = time.monotonic() - start

            print(
                f"✅ REQUEST END: "
                f"{request.method} {request.get_full_path()} "
                f"status={response.status_code} "
                f"time={elapsed:.3f}s"
            )

            return response

        except BaseException as exc:
            elapsed = time.monotonic() - start

            print(
                f"💥 REQUEST EXCEPTION: "
                f"{request.method} {request.get_full_path()} "
                f"time={elapsed:.3f}s "
                f"type={type(exc).__name__}"
            )

            raise


@database_sync_to_async
def get_user_and_github_token_from_db(user_id: Any):
    """
    Look up the user in my database and safely decrypt my stored GitHub access token
    from the profile. This serves as my primary fallback when the Redis cache misses.
    """
    User = get_user_model()
    try:
        user = User.objects.select_related("user_profile").get(id=user_id)
        github_token = None
        if hasattr(user, "user_profile") and user.user_profile.encrypted_access_token:
            try:
                decrypted = decrypt_token(user.user_profile.encrypted_access_token)
                github_token = decrypted.decode("utf-8") if isinstance(decrypted, bytes) else decrypted
            except Exception as e:
                print(f"⚠️ [WS-AUTH] Decrypting my GitHub access token failed: {e}")
        print(f"🔍 [WS-AUTH] Database lookup successful for User ID {user_id}: {user.username}")
        return user, github_token
    except User.DoesNotExist:
        print(f"❌ [WS-AUTH] Database lookup failed. No user found matching ID: {user_id}")
        return AnonymousUser(), None


class CookieJwtAuthMiddleware(BaseMiddleware):
    """
    ASGI middleware to authenticate incoming WebSocket connections via my HttpOnly JWT cookie.
    If authentication fails, I assign an AnonymousUser to my connection scope and let downstream
    consumers handle the rejection cleanly (e.g. close code 4001).
    I must never return an HttpResponse here, because ASGI WebSocket pipelines require WebSocket events.
    """

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> Any:
        # Default to anonymous user and null GitHub token
        scope["user"] = AnonymousUser()
        scope["github_token"] = None

        # 1. Parse incoming cookies header string
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("utf-8")

        cookies = {}
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                k, v = cookie.strip().split("=", 1)
                cookies[k] = v

        # 2. Extract my secure JWT access token (from cookie or optional query param fallback)
        encrypted_jwt = cookies.get("jwt_access_token")
        if not encrypted_jwt and scope.get("query_string"):
            query_params = parse_qs(scope["query_string"].decode("utf-8"))
            encrypted_jwt = query_params.get("token", [None])[0]

        if encrypted_jwt:
            try:
                # 3. Clean token string
                token_string = encrypted_jwt.decode("utf-8") if isinstance(encrypted_jwt, bytes) else encrypted_jwt

                # 4. Verify cryptographic signature locally
                parsed_jwt = AccessToken(token_string)
                user_id = parsed_jwt.get("id") or parsed_jwt.get("user_id")

                # 5. Look up user and stored GitHub token in my database
                user, db_github_token = await get_user_and_github_token_from_db(user_id)
                scope["user"] = user

                # 6. Prefer cached GitHub credentials if available, otherwise use my database token
                details_cache_key = f"user:repos:{user_id}"
                cached_details = cache.get(details_cache_key)
                if cached_details and isinstance(cached_details, dict) and cached_details.get("github_access_token"):
                    scope["github_token"] = cached_details["github_access_token"]
                elif db_github_token:
                    scope["github_token"] = db_github_token

            except Exception as e:
                print(f"💥 [WS-AUTH] CRITICAL REJECTION: Token parsing failed! Error: {str(e)}")
                scope["user"] = AnonymousUser()
        else:
            print("⚠️ [WS-AUTH] REJECTION: 'jwt_access_token' cookie was entirely missing from WebSocket handshake headers.")
            scope["user"] = AnonymousUser()

        print("--- 📡 FORWARDING TO CONSUMER ROUTER ---")
        return await self.inner(scope, receive, send)



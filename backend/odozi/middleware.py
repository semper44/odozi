# middleware.py
from urllib.parse import parse_qs
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from odozi.utils.authentication import get_user_from_github_token

class TicketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        
        # Extract the transient ticket parameter
        ticket_list = query_params.get("ticket", [None])
        ticket = ticket_list[0]
        
        if not ticket:
            scope["user"] = AnonymousUser()
            return await super().__call__(scope, receive, send)
            
        redis_key = f"ws_ticket:{ticket}"
        
        # In-memory fast path lookup via Redis
        github_token = cache.get(redis_key)
        
        if github_token:
            # INSTANT DESTRUCTION / BURN RULE
            cache.delete(redis_key)
            
            # Authenticate against GitHub and map user instance
            user = await get_user_from_github_token(github_token)
            scope["user"] = user if user else AnonymousUser()
        else:
            # Reused, manipulated, or expired ticket instantly rejected
            scope["user"] = AnonymousUser()
            
        return await super().__call__(scope, receive, send)

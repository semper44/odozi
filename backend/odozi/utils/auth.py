# odozi/utils/authentication.py
import logging
from django_user_agents.utils import get_user_agent
from account_profile.models import UserProfileModel

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Extracts the true client IP address, accounting for reverse proxies like Render/Vercel."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_browser_family(request):
    """Extracts just the core browser application engine name (e.g., 'Chrome', 'Firefox')."""
    user_agent = get_user_agent(request)
    return user_agent.browser.family # Returns standard clean strings

def invalidate_user_session(user):
    """
    CRITICAL THREAT RESPONSE: Destroys user's active GitHub credentials instantly 
    in the database if an interception race condition occurs.
    """
    logger.critical(f"🚨 SECURITY ALERT: Token intercept attempt detected for user: {user.username}!")
    try:
        profile = UserProfileModel.objects.get(user=user)
        profile.encrypted_access_token = None
        profile.encrypted_refresh_token = None
        profile.save()
        logger.warning(f"🔒 Application tokens forcefully wiped for user: {user.username}.")
    except UserProfileModel.DoesNotExist:
        pass

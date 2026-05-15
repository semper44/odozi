from allauth.account.adapter import DefaultAccountAdapter
from django.forms import ValidationError

class NoPasswordRegistrationAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Blocks traditional username/password form registration.
        """
        return False

    def is_safe_url(self, url):
        # Keeps internal API redirects safe
        return True

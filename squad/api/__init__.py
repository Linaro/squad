from django.core.cache import cache
from rest_framework.throttling import UserRateThrottle


class SocialUserRateThrottle(UserRateThrottle):
    """
    Limits the rate of API calls that may be made by a given social user.

    The user id will be used as a unique cache key if the user is
    authenticated.  For anonymous requests, the IP address of the request will
    be used.
    """

    scope = "socialuser"

    def is_social_user(self, user):
        """
        Social account user might use multiple applications (github, gitlab, google, ...)
        to log in. But all of the login applications would likely point to the same
        django user, which is what we want to rate limit here.
        """

        key = f"socialuser#{user.id}"
        from allauth.socialaccount.models import SocialAccount
        return cache.get_or_set(key, SocialAccount.objects.filter(user_id=user.id).exists())

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            if not self.is_social_user(request.user):
                # do not throttle non-social users
                return None

            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident
        }

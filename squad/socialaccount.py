from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login

from squad.core.models import User


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.username = user.email
        return user

    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if user.id:
            return
        try:
            existing_user = User.objects.get(username=user.username)
            sociallogin.state['process'] = 'connect'
            perform_login(request, existing_user, request.GET.get('next', '/'))
        except User.DoesNotExist:
            pass

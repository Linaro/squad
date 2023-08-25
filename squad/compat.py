"""
SQUAD compatibity file
"""
from rest_framework_extensions import __version__ as DRFE_VERSION_STR
from allauth import __version__ as DAA_VERSION_STR

DRFE_VERSION = [int(n) for n in DRFE_VERSION_STR.split(".")]
DAA_VERSION = [int(n) for n in DAA_VERSION_STR.split(".")]

# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend # noqa
except ImportError:
    from rest_framework_filters.backends import DjangoFilterBackend as RestFrameworkFilterBackend # noqa

try:
    from rest_framework_filters.backends import ComplexFilterBackend # noqa
except ImportError:
    from squad.api.filters import ComplexFilterBackend # noqa


def drf_basename(name):
    """
    Handles compatibility with different versions of djangorestframework, in
    terms of the deprecation of `base_name` when registering ViewSets on DRF >=
    3.10.
    """
    if DRFE_VERSION >= [0, 6]:
        return {"basename": name}
    else:
        return {"base_name": name}


def get_socialaccount_provider(providers, socialapp, request):
    """
    Django-allauth 0.55 removed the function `by_id`
    Ref: https://github.com/pennersr/django-allauth/commit/cc5279bb61dba9cf0fafb10f4ae175c018749f1f
    """

    if DAA_VERSION >= [0, 55]:
        return socialapp.get_provider(request)
    else:
        return providers.registry.by_id(socialapp.provider)

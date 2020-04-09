"""
SQUAD compatibity file
"""
from rest_framework_extensions import __version__ as DRFE_VERSION_STR

DRFE_VERSION = [int(n) for n in DRFE_VERSION_STR.split(".")]

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

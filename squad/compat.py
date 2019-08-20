"""
SQUAD compatibity file
"""

# Handles compatibility for django_restframework_filters
try:
    from rest_framework_filters.backends import RestFrameworkFilterBackend # noqa
except ImportError:
    from rest_framework_filters.backends import DjangoFilterBackend as RestFrameworkFilterBackend # noqa

try:
    from rest_framework_filters.backends import ComplexFilterBackend # noqa
except ImportError:
    from squad.api.filters import ComplexFilterBackend # noqa

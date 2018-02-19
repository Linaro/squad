from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from enum import Enum
from rest_framework.authtoken.models import Token


from squad.core import models


class AuthMode(Enum):
    READ = 0
    WRITE = 1


def auth_write(func):
    return auth(func, AuthMode.WRITE)


def auth(func, mode=AuthMode.READ):
    def auth_wrapper(*args, **kwargs):
        request = args[0]
        group_slug = args[1]
        project_slug = args[2]

        group = get_object_or_404(models.Group, slug=group_slug)
        project = get_object_or_404(group.projects, slug=project_slug)

        tokenkey = request.META.get('HTTP_AUTH_TOKEN', None)
        user = request.user
        token = None
        if tokenkey:
            try:
                # truncate keys at 40 characters since djangorestframework's
                # Token keys are limited to 40 characters
                token = Token.objects.get(key=tokenkey[0:40])
                user = token.user
            except Token.DoesNotExist:
                pass

        if not (project.is_public or user.is_authenticated or token):
            raise PermissionDenied()

        if (mode == AuthMode.READ and project.is_public) or project.writable_by(user):
            # authentication OK, call the original view
            return func(*args, **kwargs)
        else:
            # `401 Authentication needed` on purpose, and not `403 Forbidden`.
            # If you don't have credentials, you are not allowed to know
            # whether that given team/project exists at all
            raise PermissionDenied()

    return auth_wrapper


def read_file_upload(stream):
    data = bytes()
    for chunk in stream.chunks():
        data = data + chunk
    return data

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from enum import Enum


from squad.core import models


def valid_token(token, project):
    return models.Token.objects.filter(key=token).filter(
        Q(project=project) | Q(project=None)
    ).exists()


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

        token = request.META.get('HTTP_AUTH_TOKEN', None)
        user = request.user

        if not (project.is_public or user.is_authenticated or token):
            raise PermissionDenied()

        if (mode == AuthMode.READ and (project.is_public or project.accessible_to(user))) or valid_token(token, project):
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

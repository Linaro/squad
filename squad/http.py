from django.http import HttpResponse
from django.shortcuts import get_object_or_404


from squad.core import models


def auth(func):
    def auth_wrapper(*args, **kwargs):
        request = args[0]
        group_slug = args[1]
        project_slug = args[2]

        group = get_object_or_404(models.Group, slug=group_slug)
        project = get_object_or_404(group.projects, slug=project_slug)

        token = request.META.get('HTTP_AUTH_TOKEN', None)
        user = request.user

        if not (project.is_public or user.is_authenticated or token):
            return HttpResponse('Authentication needed', status=401)

        if project.is_public or project.tokens.filter(key=token).exists() or project.accessible_to(user):
            # authentication OK, call the original view
            return func(*args, **kwargs)
        else:
            # `401 Authentication needed` on purpose, and not `403 Forbidden`.
            # If you don't have credentials, you are not allowed to know
            # whether that given team/project exists at all
            return HttpResponse('Authentication needed', status=401)

    return auth_wrapper

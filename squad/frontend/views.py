import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from squad.core.models import Project


PUBLIC_SITE = bool(os.getenv('SQUAD_PUBLIC_SITE'))


def login_required_on_private_site(func):
    if PUBLIC_SITE:
        return func
    else:
        return login_required(func)


@login_required_on_private_site
def home(request):
    context = {
        'projects': Project.objects.all(),
    }
    return render(request, 'squad/index.html', context)


@login_required_on_private_site
def group(request, group_slug):
    pass


@login_required_on_private_site
def project(request, group_slug, project_slug):
    pass

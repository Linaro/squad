from django.http import HttpResponse
from django.shortcuts import render

from squad.core.models import Project


def home(request):
    context = {
        'projects': Project.objects.all(),
    }
    return render(request, 'squad/index.html', context)


def group(request, group_slug):
    pass


def project(request, group_slug, project_slug):
    pass

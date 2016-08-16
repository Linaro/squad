from django.http import HttpResponse
from django.shortcuts import render


def home(request):
    return HttpResponse('hello world')


def group(request, group_slug):
    pass


def project(request, group_slug, project_slug):
    pass

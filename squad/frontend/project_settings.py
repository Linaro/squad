from django import forms
from django.conf.urls import url
from django.shortcuts import render, redirect, reverse


from squad.core.models import Project
from squad.http import auth_write
from squad.frontend.queries import get_metrics_list


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'is_public', 'description']


@auth_write
def settings(request, group, project):
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=request.project)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = ProjectForm(instance=request.project)

    context = {
        'group': request.group,
        'project': request.project,
        'form': form,
    }
    return render(request, 'squad/project_settings/index.jinja2', context)


@auth_write
def thresholds(request, group_slug, project_slug):
    project = request.project

    environments = [{"name": e.slug} for e in project.environments.order_by('id').all()]
    metrics = get_metrics_list(project)

    context = {
        "project": project,
        "environments": environments,
        "metrics": metrics,
    }
    return render(request, 'squad/project_settings/thresholds.jinja2', context)


@auth_write
def thresholds_legacy(request, group_slug, project_slug):
    return redirect(reverse('project-settings-thresholds', args=[group_slug, project_slug]))


urls = [
    url('^$', settings, name='project-settings'),
    url(r'^thresholds/$', thresholds, name='project-settings-thresholds'),
]

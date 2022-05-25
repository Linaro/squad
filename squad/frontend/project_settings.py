from django import forms
from django.urls import re_path as url
from django.shortcuts import render, redirect, reverse
from django.utils.translation import gettext_lazy as N_

from squad.core.models import Project, Environment
from squad.http import auth_write
from squad.frontend.forms import DeleteConfirmationForm


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'is_public', 'is_archived', 'description',
                  'enabled_plugins_list', 'wait_before_notification',
                  'notification_timeout', 'force_finishing_builds_on_timeout',
                  'data_retention_days', 'important_metadata_keys']


class ProjectFormAdvanced(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['project_settings']


class ProjectFormBuildConfidence(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['build_confidence_count', 'build_confidence_threshold']


class EnvironmentForm(forms.ModelForm):
    class Meta:
        model = Environment
        fields = ['slug', 'expected_test_runs']


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
def advanced_settings(request, group, project):
    if request.method == "POST":
        form = ProjectFormAdvanced(request.POST, instance=request.project)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = ProjectFormAdvanced(instance=request.project)

    context = {
        'group': request.group,
        'project': request.project,
        'form': form,
    }
    return render(request, 'squad/project_settings/advanced.jinja2', context)


@auth_write
def build_confidence(request, group, project):
    if request.method == "POST":
        form = ProjectFormBuildConfidence(request.POST, instance=request.project)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = ProjectFormBuildConfidence(instance=request.project)

    context = {
        'group': request.group,
        'project': request.project,
        'form': form,
    }
    return render(request, 'squad/project_settings/build_confidence.jinja2', context)


@auth_write
def thresholds(request, group_slug, project_slug):
    project = request.project
    environments = {}
    for env in project.environments.order_by('id').all():
        environments[env.id] = env.slug

    context = {
        "project": project,
        "environments": environments,
    }
    return render(request, 'squad/project_settings/thresholds.jinja2', context)


@auth_write
def environments(request, group_slug, project_slug):
    EnvironmentFormSet = forms.inlineformset_factory(Project, Environment, form=EnvironmentForm, extra=1)
    if request.method == "POST":
        form = EnvironmentFormSet(request.POST, instance=request.project)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = EnvironmentFormSet(instance=request.project)

    context = {
        'group': request.group,
        'project': request.project,
        'form': form,
    }
    return render(request, 'squad/project_settings/environments.jinja2', context)


@auth_write
def thresholds_legacy(request, group_slug, project_slug):
    return redirect(reverse('project-settings-thresholds', args=[group_slug, project_slug]))


class DeleteProjectForm(DeleteConfirmationForm):
    label = N_('Type the project slug (the name used in URLs) to confirm')
    no_match_message = N_('The confirmation does not match the project slug')


@auth_write
def delete(request, group_slug, project_slug):
    project = request.project
    if request.method == "POST":
        form = DeleteProjectForm(request.POST, deletable=project)
        if form.is_valid():
            project.delete()
            return redirect(reverse('group', args=[group_slug]))
    else:
        form = DeleteProjectForm(deletable=project)

    context = {
        'project': project,
        'form': form,
    }
    return render(request, 'squad/project_settings/delete.jinja2', context)


urls = [
    url('^$', settings, name='project-settings'),
    url(r'^thresholds/$', thresholds, name='project-settings-thresholds'),
    url(r'^environments/$', environments, name='project-settings-environments'),
    url(r'^build_confidence/$', build_confidence, name='project-settings-build-confidence'),
    url(r'^advanced/$', advanced_settings, name='project-advanced-settings'),
    url(r'^delete/$', delete, name='project-settings-delete'),
]

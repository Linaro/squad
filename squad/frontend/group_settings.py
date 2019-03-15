from django import forms
from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, reverse


from squad.core.models import Group
from squad.core.models import Project
from squad.frontend.forms import DeleteConfirmationForm
from squad.http import auth_write


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'description']


@auth_write
def settings(request, group_slug):
    if request.method == "POST":
        form = GroupForm(request.POST, instance=request.group)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = GroupForm(instance=request.group)

    context = {
        'group': request.group,
        'form': form,
    }
    return render(request, 'squad/group_settings/index.jinja2', context)


class DeleteGroupForm(DeleteConfirmationForm):
    label = 'Type the group slug (the name used in URLs) to confirm'
    no_match_message = 'The confirmation does not match the group slug'


@auth_write
def delete(request, group_slug):
    group = request.group
    if request.method == "POST":
        form = DeleteGroupForm(request.POST, deletable=group)
        if form.is_valid():
            group.delete()
            return redirect(reverse('home'))
    else:
        form = DeleteGroupForm(deletable=group)
    context = {
        'group': group,
        'form': form,
    }
    return render(request, 'squad/group_settings/delete.jinja2', context)


class NewGroupForm(GroupForm):
    class Meta(GroupForm.Meta):
        fields = ['slug'] + GroupForm.Meta.fields


@login_required
def new_group(request):
    if request.method == "POST":
        form = NewGroupForm(request.POST, instance=Group())
        if form.is_valid():
            group = form.save()
            group.add_admin(request.user)
            return redirect(reverse('group-settings', args=[group.slug]))
    else:
        form = NewGroupForm()

    context = {
        'form': form,
    }
    return render(request, 'squad/group_settings/new_group.jinja2', context)


class NewProjectForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].widget = forms.HiddenInput()
        self.fields['group'].disabled = True

    class Meta:
        model = Project
        fields = ['group', 'slug', 'name', 'is_public', 'description']


@auth_write
def new_project(request, group_slug):
    group = request.group
    if request.method == "POST":
        form = NewProjectForm(request.POST, instance=Project(group=group))
        if form.is_valid():
            project = form.save()
            return redirect(reverse('project-settings', args=[group.slug, project.slug]))
    else:
        form = NewProjectForm(instance=Project(group=group))

    context = {'group': group, 'form': form}
    return render(request, 'squad/group_settings/new_project.jinja2', context)


urls = [
    url('^$', settings, name='group-settings'),
    url('^delete/$', delete, name='group-delete'),
    url('^new-project/$', new_project, name='group-new-project'),
]

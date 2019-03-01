from django import forms
from django.conf.urls import url
from django.shortcuts import render, redirect


from squad.core.models import Group
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


urls = [
    url('^$', settings, name='group-settings'),
]

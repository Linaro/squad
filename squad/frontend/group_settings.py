from django import forms
from django.urls import re_path as url
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, reverse
from django.utils.translation import gettext_lazy as N_

from django.utils.decorators import method_decorator
from django.views.generic.edit import FormView, UpdateView, CreateView


from squad.core.models import Group
from squad.core.models import GroupMember
from squad.core.models import Project
from squad.frontend.forms import DeleteConfirmationForm
from squad.http import auth_write


class GroupViewMixin(object):

    def get_extra_form_kwargs(self):
        return {}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self.get_extra_form_kwargs())
        return kwargs

    @property
    def group(self):
        return self.request.group

    def get_object(self):
        return self.request.group

    def get_extra_context_data(self):
        return {}

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['group'] = self.request.group
        context.update(self.get_extra_context_data())
        return context


class GroupForm(forms.ModelForm):

    class Meta:
        model = Group
        fields = ['name', 'description']


@method_decorator(auth_write, name='dispatch')
class BaseSettingsView(GroupViewMixin, UpdateView):

    template_name = 'squad/group_settings/index.jinja2'
    form_class = GroupForm

    def get_success_url(self):
        return self.request.path


class DeleteGroupForm(DeleteConfirmationForm):

    label = N_('Type the group slug (the name used in URLs) to confirm')
    no_match_message = N_('The confirmation does not match the group slug')


@method_decorator(auth_write, name='dispatch')
class DeleteGroupView(GroupViewMixin, FormView):

    template_name = 'squad/group_settings/delete.jinja2'
    form_class = DeleteGroupForm

    def get_extra_form_kwargs(self):
        return {'deletable': self.group}

    def form_valid(self, form):
        for project in self.group.projects.all():
            project.delete()
        self.group.delete()
        return redirect(reverse('home'))


class GroupRelationshipForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].widget = forms.HiddenInput()
        self.fields['group'].disabled = True


class GroupMemberForm(GroupRelationshipForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = self.fields['user'].queryset.order_by('username')

    class Meta:
        model = GroupMember
        fields = ['group', 'user', 'access']


class GroupFormAdvanced(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['settings']


@method_decorator(auth_write, name='dispatch')
class GroupMembersView(GroupViewMixin, FormView):

    template_name = 'squad/group_settings/members.jinja2'
    form_class = GroupMemberForm

    def dispatch(self, *args, **kwargs):
        method = self.request.POST.get('_method', '').lower()
        if method == 'delete':
            return self.delete(*args, **kwargs)
        elif method == 'put':
            return self.put(*args, **kwargs)
        else:
            return super().dispatch(*args, **kwargs)

    def __get_member__(self):
        member_id = int(self.request.POST['member_id'])
        return GroupMember.objects.filter(group=self.group).get(pk=member_id)

    def put(self, *args, **kwargs):
        member = self.__get_member__()
        member.access = self.request.POST['access']
        member.full_clean()
        member.save()
        return redirect(self.request.path)

    def delete(self, *args, **kwargs):
        self.__get_member__().delete()
        return redirect(self.request.path)

    def form_valid(self, form):
        form.save()
        return redirect(self.request.path)

    def get_initial(self):
        return {'group': self.group.id}

    def get_extra_context_data(self):
        return {
            'members': GroupMember.objects.filter(group=self.group).prefetch_related('user').all(),
            'access': GroupMember._meta.get_field('access').choices,
        }


class NewGroupForm(GroupForm):

    class Meta(GroupForm.Meta):
        fields = ['slug'] + GroupForm.Meta.fields


@method_decorator(login_required, name='dispatch')
class NewGroupView(CreateView):

    template_name = 'squad/group_settings/new_group.jinja2'
    form_class = NewGroupForm

    def form_valid(self, form):
        group = form.save()
        group.add_admin(self.request.user)
        return redirect(reverse('group-settings', args=[group.slug]))


class NewProjectForm(GroupRelationshipForm):

    class Meta:
        model = Project
        fields = ['group', 'slug', 'name', 'is_public', 'description']


@method_decorator(auth_write, name='dispatch')
class NewProjectView(GroupViewMixin, CreateView):

    template_name = 'squad/group_settings/new_project.jinja2'
    form_class = NewProjectForm

    def get_extra_form_kwargs(self):
        return {'instance': Project(group=self.group)}

    def form_valid(self, form):
        project = form.save()
        return redirect(reverse('project-settings', args=[self.group.slug, project.slug]))


@auth_write
def advanced_settings(request, group):
    if request.method == "POST":
        form = GroupFormAdvanced(request.POST, instance=request.group)
        if form.is_valid():
            form.save()
            return redirect(request.path)
    else:
        form = GroupFormAdvanced(instance=request.group)

    context = {
        'group': request.group,
        'form': form,
    }
    return render(request, 'squad/group_settings/advanced.jinja2', context)


urls = [
    url('^$', BaseSettingsView.as_view(), name='group-settings'),
    url('^members/$', GroupMembersView.as_view(), name='group-members'),
    url('^advanced/$', advanced_settings, name='group-advanced-settings'),
    url('^delete/$', DeleteGroupView.as_view(), name='group-delete'),
    url('^new-project/$', NewProjectView.as_view(), name='group-new-project'),
]

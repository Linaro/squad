from django import forms
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView


from squad.core.models import Build
from squad.frontend.views import get_build
from squad.http import auth_write


class BuildSettingsForm(forms.ModelForm):

    class Meta:
        model = Build
        fields = ['keep_data']


@method_decorator(auth_write, name='dispatch')
class BuildSettingsView(UpdateView):
    template_name = 'squad/build_settings.jinja2'
    form_class = BuildSettingsForm

    def get_object(self):
        return get_build(self.request.project, self.args[2])

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['group'] = self.request.group
        context['project'] = self.request.project
        return context

    def get_success_url(self):
        return self.request.path

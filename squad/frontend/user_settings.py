from django import forms
from django.conf.urls import url
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required


from squad.http import auth


@login_required
def home(request):
    return redirect(reverse('settings-profile'))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect(request.path)
        else:
            context = {'form': form}
    else:
        context = {'form': ProfileForm(instance=request.user)}
    return render(request, 'squad/user_settings/profile.html', context)


urls = [
    url('^$', home, name='settings-home'),
    url('^profile/$', profile, name='settings-profile'),
]

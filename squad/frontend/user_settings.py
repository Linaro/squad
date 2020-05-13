import logging

from django import forms
from django.conf.urls import url
from django.contrib.auth.models import User
from django.urls import reverse
from django.db.utils import IntegrityError
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect


from rest_framework.authtoken.models import Token


from squad.core.models import Group, Project, Subscription, UserNamespace


logger = logging.getLogger()


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
    return render(request, 'squad/user_settings/profile.jinja2', context)


@login_required
def api_token(request):
    try:
        token = Token.objects.get(user=request.user)
    except Token.DoesNotExist:
        token = None

    if request.method == "POST":
        if token:
            token.delete()
        token = Token.objects.create(user=request.user)
        return redirect(reverse('settings-api-token'))

    context = {'token': token}
    return render(request, 'squad/user_settings/api_token.jinja2', context)


@login_required
def subscriptions(request):

    subscriptions = Subscription.objects.filter(user=request.user)
    groups = Group.objects.all().prefetch_related('projects')

    if request.method == "POST":
        try:
            Subscription.objects.create(
                project_id=request.POST.get("subscription"),
                notification_strategy=request.POST.get(
                    "notification-strategy"),
                user=request.user
            )
        except IntegrityError:
            logger.warning("Subscription for given user %s already exists on project: %s", request.user, request.POST.get("subscription"))
            pass

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', request.path_info))

    context = {
        'subscriptions': subscriptions,
        'groups': groups,
        'notification_strategies': {elem[0]: elem[1] for elem in
                                    Subscription.STRATEGY_CHOICES},
    }
    return render(request, 'squad/user_settings/subscriptions.jinja2', context)


@login_required
def remove_subscription(request, id=None):

    subscription = None
    if request.method == "POST":
        project_id = request.POST.get("subscription")
        project = get_object_or_404(Project, pk=project_id)
        subscription = get_object_or_404(Subscription, project=project, user=request.user)
    if not subscription:
        subscription = get_object_or_404(Subscription, pk=id, user=request.user)
    subscription.delete()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', request.path_info))


@login_required
def projects(request):
    if request.method == "POST":
        UserNamespace.objects.create_for(request.user)
        return redirect(request.path)

    try:
        user_namespace = UserNamespace.objects.get_for(request.user)
    except UserNamespace.DoesNotExist:
        user_namespace = None

    context = {
        'user_namespace': user_namespace,
    }
    return render(request, 'squad/user_settings/projects.jinja2', context)


urls = [
    url('^$', home, name='settings-home'),
    url('^profile/$', profile, name='settings-profile'),
    url('^api-token/$', api_token, name='settings-api-token'),
    url('^subscriptions/$', subscriptions, name='settings-subscriptions'),
    url(r'^remove-subscription/(?P<id>\d+)$', remove_subscription, name='settings-subscription-remove'),
    url(r'^remove-subscription/$', remove_subscription, name='settings-subscription-remove-post'),
    url('^projects/$', projects, name='settings-projects'),
]

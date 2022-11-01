"""squad URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include
from django.urls import re_path as url
from django.conf import settings
from django.shortcuts import render
from django.contrib import admin
from django.http import HttpResponseNotFound, HttpResponseForbidden

import django.contrib.auth.views as auth


import json


def permission_denied(request, exception, template_name='401.jinja2'):
    return render(
        request,
        template_name,
        {
            'request': request,
            'exception': exception,
        },
        status=401,
    )


def page_not_found(request, exception, template_name='404.jinja2'):
    if hasattr(request, 'is_json') and request.is_json:
        response_data = {'detail': '%s' % exception}
        return HttpResponseNotFound(json.dumps(response_data), content_type='application/json')

    return render(
        request,
        template_name,
        {
            'request': request,
            'exception': exception,
        },
        status=404,
    )


handler403 = 'squad.urls.permission_denied'
handler404 = 'squad.urls.page_not_found'


extra_urls = []
try:
    import debug_toolbar
    extra_urls.append(url(r'^__debug__/', include(debug_toolbar.urls)))
except ImportError:
    pass


if 'health_check' in settings.INSTALLED_APPS:
    try:
        from health_check.views import MainView as MainHealthCheckView
        from squad.http import auth_user_from_request

        def health_check_view(request):
            user = auth_user_from_request(request, request.user)
            if user and user.is_staff:
                return MainHealthCheckView.as_view()(request)
            return HttpResponseForbidden()

        extra_urls.append(url(r'^ht/', health_check_view, name='health_check'))
    except ImportError:
        pass

urlpatterns = extra_urls + [
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include('squad.api.urls')),
    url(r'^login/', auth.LoginView.as_view(template_name='squad/login.jinja2')),
    url(r'^logout/', auth.LogoutView.as_view(next_page='/')),
    url(r'^accounts/', include('allauth.urls')),
    url(r'', include('squad.frontend.urls'))
]

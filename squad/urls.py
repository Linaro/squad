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
from django.conf.urls import include, url
from django.shortcuts import render_to_response
from django.contrib import admin

import django.contrib.auth.views as auth


def permission_denied(request, exception, template_name='401.jinja2'):
    return render_to_response(
        template_name,
        {
            'request': request,
            'exception': exception,
        },
        status=401,
    )


def page_not_found(request, exception, template_name='404.jinja2'):
    return render_to_response(
        template_name,
        {
            'request': request,
            'exception': exception,
        },
        status=404,
    )


handler403 = 'squad.urls.permission_denied'
handler404 = 'squad.urls.page_not_found'


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^api/', include('squad.api.urls')),
    url(r'^login/', auth.login, {'template_name': 'squad/login.jinja2'}),
    url(r'^logout/', auth.logout, {'next_page': '/'}),
    url(r'', include('squad.frontend.urls'))
]

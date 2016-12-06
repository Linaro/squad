from django.conf.urls import url

from . import views

slug_pattern = '[a-z0-9_.-]+'
urlpatterns = [
    url(r'^$', views.home, name='home'),
    url(r'^(%s)/$' % slug_pattern, views.group, name='group'),
    url(r'^(%s)/(%s)/$' % ((slug_pattern,) * 2), views.project, name='project'),
    url(r'^(%s)/(%s)/builds/$' % ((slug_pattern,) * 2), views.builds, name='builds'),
    url(r'^(%s)/(%s)/build/([^/]+)/$' % ((slug_pattern,) * 2), views.build, name='build'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/$' % ((slug_pattern,) * 2), views.test_run, name='testrun'),
    url(r'^(%s)/(%s)/charts/$' % ((slug_pattern,) * 2), views.charts, name='charts'),
]

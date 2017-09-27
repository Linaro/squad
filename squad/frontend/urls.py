from django.conf import settings
from django.conf.urls import url
from django.http import HttpResponse
from django.shortcuts import redirect

from . import views
from . import comparison
from . import tests
from . import ci
from squad.core.models import slug_pattern

urlpatterns = [
    url(r'^favicon.ico$', lambda _: redirect(settings.MEDIA_URL + '/static/favicon.ico')),
    url(r'^robots.txt$', lambda _: HttpResponse("User-agent: *\nDisallow: /\n", content_type='text/plain')),
    url(r'^$', views.home, name='home'),
    url(r'^_/compare/$', comparison.compare_projects, name='compare_projects'),
    url(r'^(%s)/$' % slug_pattern, views.group, name='group'),
    url(r'^(%s)/(%s)/$' % ((slug_pattern,) * 2), views.project, name='project'),
    url(r'^(%s)/(%s)/tests/(.*)$' % ((slug_pattern,) * 2), tests.test_history, name='test_history'),
    url(r'^(%s)/(%s)/metrics/$' % ((slug_pattern,) * 2), views.metrics, name='metrics'),
    url(r'^(%s)/(%s)/builds/$' % ((slug_pattern,) * 2), views.builds, name='builds'),
    url(r'^(%s)/(%s)/build/([^/]+)/$' % ((slug_pattern,) * 2), views.build, name='build'),
    url(r'^(%s)/(%s)/build/([^/]+)/tests/$' % ((slug_pattern,) * 2), tests.tests, name='tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testjobs/$' % ((slug_pattern,) * 2), ci.testjobs, name='testjobs'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/$' % ((slug_pattern,) * 2), views.test_run, name='testrun'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/log$' % ((slug_pattern,) * 2), views.test_run_log, name='testrun_log'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/tests$' % ((slug_pattern,) * 2), views.test_run_tests, name='testrun_tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/metrics$' % ((slug_pattern,) * 2), views.test_run_metrics, name='testrun_metrics'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/metadata$' % ((slug_pattern,) * 2), views.test_run_metadata, name='testrun_metadata'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/attachments/([^/]+)$' % ((slug_pattern,) * 2), views.attachment, name='attachment'),
    url(r'^testjob/([^/]+)$', views.test_job, name='test_job'),
]

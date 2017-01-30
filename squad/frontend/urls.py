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
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/log$' % ((slug_pattern,) * 2), views.test_run_log, name='testrun_log'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/tests$' % ((slug_pattern,) * 2), views.test_run_tests, name='testrun_tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/metrics$' % ((slug_pattern,) * 2), views.test_run_metrics, name='testrun_metrics'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/metadata$' % ((slug_pattern,) * 2), views.test_run_metadata, name='testrun_metadata'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/attachments/([^/]+)$' % ((slug_pattern,) * 2), views.attachment, name='attachment'),
    url(r'^(%s)/(%s)/charts/$' % ((slug_pattern,) * 2), views.charts, name='charts'),
]

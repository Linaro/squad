from django.conf import settings
from django.conf.urls import include, url
from django.http import HttpResponse
from django.shortcuts import redirect

from . import views
from . import comparison
from . import tests
from . import ci
from . import group_settings
from . import project_settings
from . import user_settings
from . import build_settings
from squad.core.models import slug_pattern, group_slug_pattern


group_and_project = (group_slug_pattern, slug_pattern)


urlpatterns = [
    url(r'^favicon.ico$', lambda _: redirect(settings.MEDIA_URL + '/static/favicon.ico')),
    url(r'^robots.txt$', lambda _: HttpResponse("User-agent: *\nDisallow: /\n", content_type='text/plain')),
    url(r'^$', views.home, name='home'),
    url(r'^_/compare/$', comparison.compare_projects, name='compare_projects'),
    url(r'^_/comparetest/$', comparison.compare_test, name='compare_test'),
    url(r'^_/comparebuilds/$', comparison.compare_builds, name='compare_builds'),
    url(r'^_/settings/', include(user_settings.urls)),
    url(r'^_/new-group/', group_settings.NewGroupView.as_view(), name='new-group'),
    url(r'^_/group-settings/(%s)/' % group_slug_pattern, include(group_settings.urls)),
    url(r'^(%s)/$' % group_slug_pattern, views.group_home, name='group'),
    url(r'^(%s)/(%s)/$' % group_and_project, views.project_home, name='project'),
    url(r'^(%s)/(%s)/settings/' % group_and_project, include(project_settings.urls)),
    url(r'^(%s)/(%s)/tests/(.+)$' % group_and_project, tests.legacy_test_history, name='legacy_test_history'),
    url(r'^(%s)/(%s)/thresholds/' % group_and_project, project_settings.thresholds_legacy),
    url(r'^(%s)/(%s)/badge$' % group_and_project, views.project_badge, name='project_badge'),
    url(r'^(%s)/(%s)/metrics/$' % group_and_project, views.metrics, name='metrics'),
    url(r'^(%s)/(%s)/knownissues/$' % group_and_project, views.known_issues, name='knownissues'),
    url(r'^(%s)/(%s)/builds/$' % group_and_project, views.builds, name='builds'),
    url(r'^(%s)/(%s)/build/([^/]+)/$' % group_and_project, views.build, name='build'),
    url(r'^(%s)/(%s)/build/([^/]+)/badge$' % group_and_project, views.build_badge, name='build_badge'),
    url(r'^(%s)/(%s)/build/([^/]+)/tests/$' % group_and_project, tests.tests, name='tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testjobs/$' % group_and_project, ci.testjobs, name='testjobs'),
    url(r'^(%s)/(%s)/build/([^/]+)/metadata/$' % group_and_project, views.build_metadata, name='build_metadata'),
    url(r'^(%s)/(%s)/build/([^/]+)/settings/$' % group_and_project, build_settings.BuildSettingsView.as_view(), name='build_settings'),
    url(r'^(%s)/(%s)/build/([^/]+)/attachments/testrun/([^/]+)/([^/]+)$' % group_and_project, views.build_attachment, name='build_attachments'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/tests/$' % group_and_project, views.test_run_suite_tests, name='testrun_suite_tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/history/$' % group_and_project, tests.test_history, name='test_history'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/details/$' % group_and_project, views.test_run_suite_test_details, name='testrun_suite_test_details'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/metrics/$' % group_and_project, views.test_run_suite_metrics, name='testrun_suite_metrics'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/log$' % group_and_project, views.test_details_log, name='test_details_log'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/tests$' % group_and_project, views.test_details_tests, name='test_details_tests'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/metrics$' % group_and_project, views.test_details_metrics, name='test_details_metrics'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/metadata$' % group_and_project, views.test_details_metadata, name='test_details_metadata'),
    url(r'^(%s)/(%s)/build/([^/]+)/testrun/([^/]+)/suite/([^/]+)/test/([^/]+)/attachments/([^/]+)$' % group_and_project, views.attachment, name='attachment'),
    url(r'^testjob/(\d+)$', views.test_job, name='test_job'),
    url(r'^(%s)/(%s)/toggle-outlier-metric/([^/]+)$' % group_and_project, views.toggle_outlier_metric, name='toggle_outlier_metric'),

]

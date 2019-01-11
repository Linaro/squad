from django.conf.urls import include, url
from rest_framework.schemas import get_schema_view

from . import views
from . import data
from . import ci
from . import rest


from squad.core.models import slug_pattern


schema_view = get_schema_view(title="SQUAD API")

urlpatterns = [
    url(r'^', include(rest.router.urls)),
    url(r'^schema/', schema_view),
    url(r'^auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^createbuild/(%s)/(%s)/(%s)' % ((slug_pattern,) * 3), views.create_build),
    url(r'^submit/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), views.add_test_run),
    url(r'^submitjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.submit_job),
    url(r'^watchjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.watch_job),
    url(r'^data/(%s)/(%s)' % ((slug_pattern,) * 2), data.get),
    url(r'^resubmit/([0-9]+)', ci.resubmit_job),
    url(r'^forceresubmit/([0-9]+)', ci.force_resubmit_job),
]

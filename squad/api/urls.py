from django.conf.urls import url
from django.shortcuts import redirect


from . import views
from . import data
from . import ci


from squad.core.models import slug_pattern


urlpatterns = [
    url(r'^$', lambda request: redirect('/')),
    url(r'^submit/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), views.add_test_run),
    url(r'^submitjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.submit_job),
    url(r'^watchjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.watch_job),
    url(r'^data/(%s)/(%s)' % ((slug_pattern,) * 2), data.get),
    url(r'^resubmit/([0-9]+)', ci.resubmit_job),
    url(r'^forceresubmit/([0-9]+)', ci.force_resubmit_job),
]

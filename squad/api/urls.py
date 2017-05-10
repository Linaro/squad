from django.conf.urls import url
from django.shortcuts import redirect


from . import views
from . import data
from . import ci


slug_pattern = '[a-z0-9_.-]+'


urlpatterns = [
    url(r'^$', lambda request: redirect('/')),
    url(r'^submit/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), views.add_test_run),
    url(r'^submitjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.submit_job),
    url(r'^watchjob/(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), ci.watch_job),
    url(r'^data/(%s)/(%s)' % ((slug_pattern,) * 2), data.get),
]

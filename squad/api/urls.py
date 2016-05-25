from django.conf.urls import url


from . import views


slug_pattern = '[a-z0-9_.-]+'


urlpatterns = [
    url(r'^(%s)/(%s)/(%s)/(%s)' % ((slug_pattern,) * 4), views.add_test_run),
]

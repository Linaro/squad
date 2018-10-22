import json
import yaml

from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.urls import resolve, NoReverseMatch
from django.template.defaultfilters import safe
from django.template.defaultfilters import date as django_date
from hashlib import md5
from markdown import markdown as to_markdown

from squad import version
from squad.core.utils import format_metadata
from squad.jinja2 import register_global_function, register_filter


# For DRF's compatibility with DTL
register = template.Library()


url_attributes = {
    'build': (
        lambda build: build.version,
    ),
    'testrun': (
        lambda testrun: testrun.build.version,
        lambda testrun: testrun.job_id,
    )
}


@register_global_function
def url(path, *args, **kwargs):
    try:
        return reverse(path, *args, **kwargs)
    except NoReverseMatch:
        return None


@register_global_function
def group_url(group):
    return reverse('group', args=[group.slug])


@register_global_function
def project_url(the_object):
    name = type(the_object).__name__.lower()
    if name == 'project':
        project = the_object
        args = (project.group.slug, project.slug)
    else:
        project = the_object.project
        group = project.group

        attrs = url_attributes.get(name)
        params = tuple([f(the_object) for f in attrs])

        args = (group.slug, project.slug) + params

    return reverse(name, args=args)


@register_global_function
def testrun_suite_tests_url(group, project, build, status):
    return testrun_suite_url(group, project, build, status, 'testrun_suite_tests')


@register_global_function
def testrun_suite_metrics_url(group, project, build, status):
    return testrun_suite_url(group, project, build, status, 'testrun_suite_metrics')


def testrun_suite_url(group, project, build, status, kind):
    testrun = status.test_run
    suite = status.suite
    args = (
        group.slug,
        project.slug,
        build.version,
        testrun.job_id,
        suite.slug.replace('/', '$'),  # encode / in suite names
    )
    return reverse(kind, args=args)


@register_global_function
def build_url(build):
    return reverse("build", args=(build.project.group.slug, build.project.slug, build.version))


@register_global_function
def project_section_url(project, name):
    return reverse(name, args=(project.group.slug, project.slug))


@register_global_function
def build_section_url(build, name):
    return reverse(name, args=(build.project.group.slug, build.project.slug, build.version))


# Needed to rename this function due to conflict with Django's auth module
# that already sets a global 'site_name', overwritting ours
# https://github.com/django/django/blob/master/django/contrib/auth/views.py#L99
@register_global_function
@register.simple_tag
def squad_site_name():
    return settings.SITE_NAME


@register_global_function(takes_context=True)
@register.simple_tag(takes_context=True)
def active(context, name):
    wanted = reverse(name)
    path = context['request'].path
    if path == wanted:
        return 'active'
    else:
        return None


@register_global_function(takes_context=True)
def login_message(context, tag, classes):
    msg = settings.SQUAD_LOGIN_MESSAGE
    if msg:
        return '<%s class="%s">%s</%s>' % (tag, classes, msg, tag)
    else:
        return ''


@register_global_function
@register.simple_tag
def squad_version():
    return version.__version__


@register.filter
@register_filter
def metadata_value(v):
    return format_metadata(v, "<br/>")


@register_filter
def markdown(mkdn):
    if mkdn is None:
        return ''
    return safe(to_markdown(mkdn))


@register_filter
def get_page_list(items):
    first = max(items.number - 5, 1)
    last = min(items.number + 5, items.paginator.num_pages)
    pages = range(first, last + 1)
    return {
        "link_first": 1 not in pages,
        "head_ellipsis": 2 not in pages,
        "pages": pages,
        "tail_ellipsis": (items.paginator.num_pages - 1) not in pages,
        "link_last": items.paginator.num_pages not in pages,
    }


@register_filter
def add_class(field, class_name):
    return field.as_widget(attrs={"class": class_name})


@register_global_function
@register.simple_tag
def avatar_url(email, size=150):
    h = md5(email.encode('utf-8').strip().lower()).hexdigest()
    return 'https://www.gravatar.com/avatar/%s?s=%s&default=mm' % (h, size)


@register_filter
def date(datetime_obj, fmt=None):
    if not fmt:
        fmt = settings.DATE_FORMAT

    return django_date(datetime_obj, fmt)

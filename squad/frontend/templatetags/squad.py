from django import template
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import safe
from hashlib import md5
from markdown import markdown as to_markdown

from squad import version
from squad.core.utils import format_metadata


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


@register.simple_tag
def group_url(group):
    return reverse('group', args=[group.slug])


@register.simple_tag
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


@register.simple_tag
def testrun_suite_tests_url(status):
    return testrun_suite_url(status, 'testrun_suite_tests')


@register.simple_tag
def testrun_suite_metrics_url(status):
    return testrun_suite_url(status, 'testrun_suite_metrics')


def testrun_suite_url(status, kind):
    testrun = status.test_run
    suite = status.suite
    build = testrun.build
    project = build.project
    group = project.group
    args = (
        group.slug,
        project.slug,
        build.version,
        testrun.job_id,
        suite.slug.replace('/', '$'),  # encode / in suite names
    )
    return reverse(kind, args=args)


@register.simple_tag
def build_url(build):
    return reverse("build", args=(build.project.group.slug, build.project.slug, build.version))


@register.simple_tag
def project_section_url(project, name):
    return reverse(name, args=(project.group.slug, project.slug))


@register.simple_tag
def build_section_url(build, name):
    return reverse(name, args=(build.project.group.slug, build.project.slug, build.version))


@register.simple_tag
def site_name():
    return settings.SITE_NAME


@register.filter
def get_value(data, key):
    return data.get(key)


@register.filter
def test_result_by_build(data, build):
    return (lambda env: data.get((build, env)))


@register.filter
def test_result_by_env(f, env):
    return f(env)


@register.simple_tag(takes_context=True)
def active(context, name):
    wanted = reverse(name)
    path = context['request'].path
    if path == wanted:
        return 'active'
    else:
        return None


@register.simple_tag(takes_context=True)
def login_message(context, tag, classes):
    msg = settings.SQUAD_LOGIN_MESSAGE
    if msg:
        return '<%s class="%s">%s</%s>' % (tag, classes, msg, tag)
    else:
        return ''


@register.simple_tag
def squad_version():
    return version.__version__


@register.filter
def metadata_value(v):
    return format_metadata(v, "<br/>")


@register.filter
def markdown(mkdn):
    if mkdn is None:
        return ''
    return safe(to_markdown(mkdn))


@register.filter
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


@register.filter
def add_class(field, class_name):
    return field.as_widget(attrs={"class": class_name})


@register.simple_tag
def avatar_url(email, size=150):
    h = md5(email.encode('utf-8').strip().lower()).hexdigest()
    return 'https://seccdn.libravatar.org/avatar/%s?s=%s&default=mm' % (h, size)

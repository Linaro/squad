from django import template
from django.conf import settings
from django.core.urlresolvers import reverse


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
def project_section_url(project, name):
    return reverse(name, args=(project.group.slug, project.slug))


@register.simple_tag
def site_name():
    return settings.SITE_NAME


@register.filter
def get_value(data, key):
    return data.get(key)


@register.simple_tag(takes_context=True)
def active(context, name):
    wanted = reverse(name)
    path = context['request'].path
    if path == wanted:
        return 'active'
    else:
        return None

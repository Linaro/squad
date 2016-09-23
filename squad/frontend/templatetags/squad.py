from django import template
from django.core.urlresolvers import reverse


register = template.Library()


url_attributes = {
    'build': 'version',
}


@register.simple_tag
def project_url(the_object):
    name = type(the_object).__name__.lower()
    if name == 'project':
        project = the_object
        args = (project.group.slug, project.slug)
    else:
        project = the_object.project
        group = project.group
        attribute = url_attributes.get(name)
        obj_id = the_object.__getattribute__(attribute)
        args = (group.slug, project.slug, obj_id)

    return reverse(name, args=args)


@register.simple_tag
def project_section_url(project, name):
    return reverse(name, args=(project.group.slug, project.slug))

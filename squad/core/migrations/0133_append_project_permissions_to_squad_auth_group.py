from __future__ import unicode_literals
from django.db import migrations
import re

PERMISSIONS = ['view', 'add', 'change']
MODELS = {'core': ['Project']}


def split_on_upper_and_make_lower(name):
    split = re.findall('[A-Z][^A-Z]*', name)
    return [w.lower() for w in split]


def append_project_permissions_to_squad_auth_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    squad_group, created = Group.objects.get_or_create(name='squad')
    for app, model in MODELS.items():
        for m in model:
            ct = ContentType.objects.get_for_model(apps.get_model(app, m))
            for permission in PERMISSIONS:
                split_words = split_on_upper_and_make_lower(m)
                perm_name = 'Can {}' + (' {}' * len(split_words))
                name = perm_name.format(permission, *split_words)
                codename = '_'.join([permission, m.lower()])
                try:
                    perm = Permission.objects.get(name=name, codename=codename, content_type=ct)
                except Permission.DoesNotExist:
                    perm = Permission.objects.create(name=name, codename=codename, content_type=ct)

                squad_group.permissions.add(perm)
    User = apps.get_model('auth', 'User')
    for user in User.objects.all():
        squad_group.user_set.add(user)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0132_attachment_mimetype'),
    ]

    operations = [
        migrations.RunPython(
            append_project_permissions_to_squad_auth_group,
            reverse_code=migrations.RunPython.noop
        )
    ]

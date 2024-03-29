# Generated by Django 4.0.4 on 2022-06-06 20:19

from collections import defaultdict
from django.db import migrations


def remove_duplicates(apps, schema_editor):
    """
        BuildSummary sometimes get duplicated due to a missing `unique_together`
        constraint. This migration adds it, so we need to get rid of duplicated
        BuildSummary objects before running the migration.

        There might be a chance of failure if there is a new occurency of
        duplication DURING this migration script, which can result in failure.
        But re-running it should re-remove newly created duplicates.
    """
    duplicates = defaultdict(int)

    BuildSummary = apps.get_model('core', 'BuildSummary')
    results = BuildSummary.objects.values('build_id', 'environment_id')
    for r in results:
        key = (r['build_id'], r['environment_id'])
        duplicates[key] += 1

    for build_env in duplicates:
        if duplicates[build_env] > 1:
            build_id, env_id = build_env
            to_remove = BuildSummary.objects.filter(build_id=build_id, environment_id=env_id).order_by('id')

            # Keep the record that was first created
            for duplicated_summary in to_remove[1:]:
                duplicated_summary.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0164_django_update'),
    ]

    operations = [
        migrations.RunPython(
            remove_duplicates,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.AlterUniqueTogether(
            name='buildsummary',
            unique_together={('build', 'environment')},
        ),
    ]

# Generated by Django 4.0.4 on 2022-11-08 14:19

from django.utils import timezone
from django.db import migrations, models


def set_project_datetime(apps, schema_editor):
    """
        Project.datetime is the most updated build's datetime
    """

    Project = apps.get_model('core', 'Project')
    projects = Project.objects.annotate(most_recent_datetime=models.Max("builds__datetime"))
    for p in projects:
        if p.most_recent_datetime:
            p.datetime = p.most_recent_datetime
            p.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0166_build_is_release'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='datetime',
            field=models.DateTimeField(blank=True, default=timezone.now),
        ),
        migrations.RunPython(
            set_project_datetime,
            reverse_code=migrations.RunPython.noop
        ),
    ]

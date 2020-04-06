# Generated by Django 2.2.6 on 2020-02-26 14:42

from django.db import migrations


def populate_env_in_thresholds_and_migrate_olddata(apps, schema_editor):
    Threshold = apps.get_model('core', 'MetricThreshold')
    Environment = apps.get_model('core', 'Environment')
    existing_thresholds = Threshold.objects.all()
    for threshold in existing_thresholds:
        envs = Environment.objects.filter(project_id=threshold.project_id)
        for env in envs:
            new_threshold = Threshold(name=threshold.name,
                                      value=threshold.value,
                                      is_higher_better=threshold.is_higher_better,
                                      environment=env,
                                      project_id=threshold.project_id)
            new_threshold.save()
        threshold.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0126_metricthreshold_environment'),
    ]

    operations = [
        migrations.RunPython(
            populate_env_in_thresholds_and_migrate_olddata,
            reverse_code=migrations.RunPython.noop
        )
    ]
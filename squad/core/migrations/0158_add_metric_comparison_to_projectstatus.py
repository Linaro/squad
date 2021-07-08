# Generated by Django 2.2.24 on 2021-10-28 11:55

from django.db import migrations, models
import squad.core.utils


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0157_remove_metric_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectstatus',
            name='metric_fixes',
            field=models.TextField(blank=True, null=True, validators=[squad.core.utils.yaml_validator]),
        ),
        migrations.AddField(
            model_name='projectstatus',
            name='metric_regressions',
            field=models.TextField(blank=True, null=True, validators=[squad.core.utils.yaml_validator]),
        ),
    ]
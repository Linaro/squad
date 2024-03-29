# Generated by Django 2.2.25 on 2021-12-17 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0161_add_metricthreshold_perm_to_squad_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='build_confidence_count',
            field=models.IntegerField(default=20, help_text='Number of previous builds to compare to'),
        ),
        migrations.AddField(
            model_name='project',
            name='build_confidence_threshold',
            field=models.IntegerField(default=90, help_text='Percentage of previous builds that built successfully'),
        ),
    ]

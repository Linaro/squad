# Generated by Django 3.2.13 on 2022-05-18 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0163_hirtoricalemailtemplate_update'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectstatus',
            name='notified_on_timeout',
            field=models.BooleanField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='test',
            name='has_known_issues',
            field=models.BooleanField(null=True),
        ),
        migrations.AlterField(
            model_name='test',
            name='result',
            field=models.BooleanField(null=True),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-07-16 11:10
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0078_auto_20180711_1539'),
    ]

    operations = [
        migrations.RenameField(
            model_name='projectstatus',
            old_name='tests_known_failures',
            new_name='tests_known_failure',
        ),
        migrations.RenameField(
            model_name='status',
            old_name='tests_known_failures',
            new_name='tests_known_failure',
        ),
    ]

# Generated by Django 2.2.16 on 2020-10-26 13:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0140_increase_gerrit_password_length'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='test',
            name='name',
        ),
    ]
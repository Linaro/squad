# Generated by Django 2.2.14 on 2020-08-18 21:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0132_attachment_mimetype'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='test',
            options={},
        ),
        migrations.RemoveField(
            model_name='test',
            name='name',
        ),
    ]

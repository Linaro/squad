# Generated by Django 2.2.12 on 2020-09-10 11:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0136_attachment_storage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='data',
            field=models.BinaryField(default=None, null=True),
        ),
    ]

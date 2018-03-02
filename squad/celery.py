from __future__ import absolute_import

import os
import sys

from celery import Celery

# set the default Django settings module for the 'celery' program.
# FIXME this duplicates code in squad/manage.py
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test.settings")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squad.settings")

from django.conf import settings  # noqa

app = Celery('squad')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

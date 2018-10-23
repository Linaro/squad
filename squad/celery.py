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
app.conf.worker_hijack_root_logger = False
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# workaround missing attribute in billiard.einfo._Frame
# see https://github.com/celery/billiard/pull/257
from billiard.einfo import _Frame  # noqa
_Frame.f_back = None

from __future__ import absolute_import

import logging
import os
import resource
import sys
import time

from celery import Celery
from celery import Task


# set the default Django settings module for the 'celery' program.
# FIXME this duplicates code in squad/manage.py
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test.settings")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squad.settings")

from django.conf import settings  # noqa


class MemoryUseLoggingTask(Task):

    def __call__(self, *args, **kwargs):
        ram0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # in kB
        try:
            return super(MemoryUseLoggingTask, self).__call__(*args, **kwargs)
        finally:
            ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # in kB
            diff = ram - ram0
            if diff >= 1024:  # 1024kB = 1048576 (1MB)
                logger = logging.getLogger()
                mb = diff / 1024
                logger.warning('Task %s%r consumed %dMB of memory', self.name, args, mb)


class SquadCelery(Celery):

    def task(self, *args, **kwargs):
        kw = {'base': MemoryUseLoggingTask}
        kw.update(kwargs)
        return super(SquadCelery, self).task(*args, **kw)

    def send_task(self, *args, **options):

        if settings.CELERY_BROKER_URL and settings.CELERY_BROKER_URL.startswith('sqs'):
            options['MessageGroupId'] = str(time.time())

        return super(SquadCelery, self).send_task(*args, **options)


app = SquadCelery('squad')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.worker_hijack_root_logger = False
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# workaround missing attribute in billiard.einfo._Frame
# see https://github.com/celery/billiard/pull/257
from billiard.einfo import _Frame  # noqa
_Frame.f_back = None

from __future__ import absolute_import
import os

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
try:
    from .celery import app as celery_app  # noqa
except ImportError as e:
    if not os.environ.get('SQUAD_GIT_BUILD'):
        raise e

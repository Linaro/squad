from squad.settings import *  # noqa
import logging


LOGGING['loggers']['django']['level'] = 999  # noqa
LOGGING['loggers']['']['level'] = 999  # noqa

# see  https://github.com/evansd/whitenoise/issues/94
MIDDLEWARE_CLASSES.remove('whitenoise.middleware.WhiteNoiseMiddleware')  # noqa
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

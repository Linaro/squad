from squad.settings import *  # noqa


LOGGING['loggers']['django']['level'] = 999  # noqa
LOGGING['loggers']['']['level'] = 999  # noqa

# see  https://github.com/evansd/whitenoise/issues/94
MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')  # noqa

# disable django_toolbar if present
try:
    MIDDLEWARE.remove('debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa
    INSTALLED_APPS.remove('debug_toolbar')  # noqa
except ValueError:
    pass

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
MEDIA_ROOT = 'test/storage'

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

TEST_RUNNER = 'test.Runner'

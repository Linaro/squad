from squad.settings import *  # noqa
import logging

logging.disable(logging.CRITICAL)

# see  https://github.com/evansd/whitenoise/issues/94
MIDDLEWARE_CLASSES.remove('whitenoise.middleware.WhiteNoiseMiddleware')  # noqa
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

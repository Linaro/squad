from squad.settings import *  # noqa

LOGGING = {}

# see  https://github.com/evansd/whitenoise/issues/94
MIDDLEWARE_CLASSES.remove('whitenoise.middleware.WhiteNoiseMiddleware')  # noqa
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

from squad.settings import *  # noqa
import logging

# settings to speed up tests
# source: http://www.daveoncode.com/2013/09/23/effective-tdd-tricks-to-speed-up-django-tests-up-to-10x-faster/
PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)
DEBUG = False
TEMPLATE_DEBUG = False
logging.disable(logging.CRITICAL)


# see  https://github.com/evansd/whitenoise/issues/94
MIDDLEWARE_CLASSES.remove('whitenoise.middleware.WhiteNoiseMiddleware')  # noqa
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

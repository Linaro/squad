from django.test import TestCase
from django.conf import settings
from django.conf import global_settings
from glob import glob
from os.path import dirname, basename


class TestI18N(TestCase):

    def test_locales_supported_by_django(self):
        django_languages = set(lng for lng, _ in global_settings.LANGUAGES)
        languages = glob('%s/squad/*/locale/*/LC_MESSAGES' % settings.BASE_DIR)
        languages = set(basename(dirname(lng.lower().replace('_', '-'))) for lng in languages)
        intersection = django_languages & languages
        self.assertEqual(intersection, languages, 'language code not supported by Django. Must be one of %r' % sorted(django_languages))

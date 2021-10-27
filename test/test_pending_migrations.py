from io import StringIO
from unittest import TestCase


from django.core import management


import pytest


@pytest.mark.django_db
class TestPendingMigrations(TestCase):
    def test_pending_migrations(self):
        output = StringIO()
        management.call_command('makemigrations', '--dry-run', stdout=output)

        expected_output = 'No changes detected\n'
        pending_migrations = output.getvalue()
        if expected_output != pending_migrations:
            print('There are pending migrations:')
            print(pending_migrations)

        self.assertEqual(expected_output, pending_migrations)

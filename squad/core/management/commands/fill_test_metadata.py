import logging

from django.core.management.base import BaseCommand

from squad.core.models import Test, SuiteMetadata


logger = logging.getLogger()


class Command(BaseCommand):

    help = """Get or create SuiteMetadata objects to fill tests that have metadata == NULL"""

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, help='How many tests to process at once. Use this to prevent OOM errors')
        parser.add_argument('--show-progress', action='store_true', help='Prints out one dot every 1000 (one thousand) tests processed')

    def handle(self, *args, **options):
        show_progress = options['show_progress']
        batch_size = options['batch_size']
        logger.info("Filling metadata for %s tests" % (batch_size if batch_size else 'all'))
        tests = Test.objects.filter(metadata__isnull=True).prefetch_related('suite')

        if batch_size:
            tests = tests[:batch_size]

        count_processed = 0
        for test in tests:
            metadata, _ = SuiteMetadata.objects.get_or_create(suite=test.suite.slug, name=test.name, kind='test')
            test.metadata = metadata
            test.save()

            count_processed += 1
            if count_processed % 1000 == 0 and show_progress:
                print('.', end='', flush=True)

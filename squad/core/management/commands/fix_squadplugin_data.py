import logging

from django.db.models import Q, F
from django.core.management.base import BaseCommand

from squad.core.models import Test, SuiteMetadata


logger = logging.getLogger()


class Command(BaseCommand):

    help = """fix suite in SuiteMetadata for cts/vts tests"""

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, help='How many tests to process at once. Use this to prevent OOM errors')
        parser.add_argument('--show-progress', action='store_true', help='Prints out one dot every 1000 (one thousand) tests processed')

    def handle(self, *args, **options):
        show_progress = options['show_progress']
        batch_size = options['batch_size']
        android_suites = ['cts', 'vts']
        condition = Q(suite__slug__icontains=android_suites[0])
        condition |= Q(suite__slug__icontains=android_suites[1])
        logger.info("fetching %s tests" % (batch_size if batch_size else 'all'))
        tests = Test.objects.filter(condition).exclude(metadata__suite=F('suite__slug')).prefetch_related('suite', 'metadata').defer('log')
        if batch_size:
            tests = tests[:batch_size]
        count_processed = 0

        buggy_metadata = set()

        for test in tests:
            if test.metadata.suite != test.suite.slug:
                metadata, _ = SuiteMetadata.objects.get_or_create(kind='test', suite=test.suite.slug, name=test.name)
                buggy_metadata.add(metadata)
                test.metadata = metadata
                test.save()
            count_processed += 1
            if count_processed % 1000 == 0 and show_progress:
                print('.', end='', flush=True)

        deleted_metadata_count = 0
        for metadata in buggy_metadata:
            test_count = Test.objects.filter(metadata=metadata).count()
            if test_count == 0:
                metadata.delete()
                deleted_metadata_count += 1

        print('Deleted %d buggy metadata objects' % deleted_metadata_count)

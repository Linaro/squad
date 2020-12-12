import logging
import math
import threading

from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery, F, Q
from django.db import IntegrityError
from squad.core.models import SuiteMetadata, Test
from squad.core.utils import split_list


correct_metadata = SuiteMetadata.objects.filter(kind='test', suite=OuterRef('suite__slug'), name=OuterRef('metadata__name'))

first_test = Test.objects.order_by().filter(metadata=OuterRef('pk')).annotate(correct_metadata=Subquery(correct_metadata.values('id')[:1]))

correct_slug = Test.objects.order_by().filter(metadata=OuterRef('pk')).annotate(suite_slug=F('suite__slug'))

annotations = {
    'correct_metadata_id': Subquery(first_test.values('correct_metadata')[:1]),
    'correct_suite_slug': Subquery(correct_slug.values('suite_slug')[:1])
}

buggy_ones = Q(suite__startswith='armeabi') | Q(suite__startswith='arm64')


logger = logging.getLogger()
STEP = 1000


class SuiteMetadataFixThread(threading.Thread):
    def __init__(self, thread_id, suitemetadata_ids, show_progress=False):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.suitemetadata_ids = suitemetadata_ids
        self.show_progress = show_progress

    def run(self):
        count = len(self.suitemetadata_ids)
        logger.info('[thread-%s] processing %d suitemetadata' % (self.thread_id, count))
        orphan_metadata = []
        for offset in range(0, count, STEP):
            ids = self.suitemetadata_ids[offset:offset + STEP]
            for metadata in SuiteMetadata.objects.filter(id__in=ids).annotate(**annotations).all():
                # It means there's no SuiteMetadata with fixed suite, so it's safe to change it in place
                if metadata.correct_metadata_id is None:
                    if metadata.correct_suite_slug is None:
                        orphan_metadata.append(metadata.id)
                    else:
                        try:
                            metadata.suite = metadata.correct_suite_slug
                            metadata.save()
                        except IntegrityError:
                            logger.error('There appears to have a fixed suite metadata already')
                            logger.error('This was not supposed to happen though, check these cases carefuly')
                            logger.error('SuiteMetadata (id: %d, kind=test, suite="%s", name="%s")' % (metadata.id, metadata.suite, metadata.name))
                            return
                # It means there's a correct one, so just update tests
                else:
                    Test.objects.order_by().filter(metadata=metadata).update(metadata_id=metadata.correct_metadata_id)
                    # It's safe to delete buggy metadata now
                    orphan_metadata.append(metadata.id)

            if self.show_progress:
                print('.', end='', flush=True)

        if len(orphan_metadata) > 0:
            logger.info('Deleting %d orphan metadata objects' % len(orphan_metadata))
            chunks = split_list(orphan_metadata, chunk_size=10000)
            for chunk in chunks:
                SuiteMetadata.objects.filter(id__in=chunk).delete()

        logger.info('[thread-%s] done updating' % self.thread_id)


class Command(BaseCommand):

    help = """helper that fixes buggy SuiteMetadata objects"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-progress',
            action='store_true',
            help='Prints out one dot every 1000 (one thousand) metadata processed'
        )
        parser.add_argument(
            '--num-threads',
            type=int,
            default=2,
            help='Number of simultaneous parallel threads to work'
        )

    def handle(self, *args, **options):
        show_progress = options['show_progress']
        num_threads = options['num_threads']

        logger.info('Discovering number of metadata that need work...')
        count = int(SuiteMetadata.objects.filter(buggy_ones).count())

        if count == 0:
            logger.info('Nothing to do!')
            return

        logger.info('Working on %d metadatas' % count)
        metadata_ids = SuiteMetadata.objects.filter(buggy_ones).order_by('-id').values_list('id', flat=True)

        chunk_size = math.floor(len(metadata_ids) / num_threads) + 1
        chunks = split_list(metadata_ids, chunk_size=chunk_size)

        threads = []
        for chunk in chunks:
            thread_id = len(threads)
            thread = SuiteMetadataFixThread(thread_id, chunk, show_progress=show_progress)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        logger.info('Done updating')

        # Check that everything worked as expected
        count = int(SuiteMetadata.objects.filter(buggy_ones).count())
        if count > 0:
            logger.error('Something went wrong! %d metadata are still buggy' % count)
            return

        logger.info('Done!')

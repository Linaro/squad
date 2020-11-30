import logging
import math
import threading

from django.core.management.base import BaseCommand

from squad.core.models import Test, TestRun
from squad.core.utils import split_list


logger = logging.getLogger()
STEP = 1000
total_updates = {}


class DataFillerThread(threading.Thread):
    def __init__(self, thread_id, testrun_ids, show_progress=False):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.testrun_ids = testrun_ids
        self.show_progress = show_progress

    def run(self):
        count = len(self.testrun_ids)
        logger.info('[thread-%s] processing %d testruns' % (self.thread_id, count))
        count_updates = 0
        for offset in range(0, count, STEP):
            ids = self.testrun_ids[offset:offset + STEP]
            for testrun in TestRun.objects.filter(id__in=ids).only('build_id', 'environment_id').all():
                count_updates += testrun.tests.update(build_id=testrun.build_id, environment_id=testrun.environment_id)

            if self.show_progress:
                print('.', end='', flush=True)

        total_updates[self.thread_id] = count_updates
        logger.info('[thread-%s] done updating %d tests' % (self.thread_id, count_updates))


class Command(BaseCommand):

    help = """helper that populates build and environment columns in test table"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-progress',
            action='store_true',
            help='Prints out one dot every 1000 (one thousand) testruns processed'
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

        logger.info('Discovering number of tests that need work...')
        count = Test.objects.filter(build__isnull=True, environment__isnull=True).count()

        if count == 0:
            logger.info('Nothing to do!')
            return

        logger.info('Working on %d tests' % count)
        testrun_ids = TestRun.objects.order_by('-id').values_list('id', flat=True)

        chunk_size = math.floor(len(testrun_ids) / num_threads) + 1
        chunks = split_list(testrun_ids, chunk_size=chunk_size)

        threads = []
        for chunk in chunks:
            thread_id = len(threads)
            total_updates[thread_id] = 0
            thread = DataFillerThread(thread_id, chunk, show_progress=show_progress)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        logger.info('Done updating %d tests' % sum(total_updates.values()))

        # Check that everything worked as expected
        count = Test.objects.filter(build__isnull=True, environment__isnull=True).count()
        if count > 0:
            logger.error('Something went wrong! %d tests still do not have build and environment filled out' % count)
            return

        logger.info('Done!')

import math
import multiprocessing
import threading

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q

from squad.core.models import Attachment, TestRun
from squad.core.utils import split_list


STEP = 1000


class TestRunFileExporterThread(threading.Thread):
    def __init__(self, thread_id, testrun_ids, show_progress=False):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.testrun_ids = testrun_ids
        self.show_progress = show_progress

    def run(self):
        count = len(self.testrun_ids)
        print('[thread-%s] processing %d testruns' % (self.thread_id, count))
        for offset in range(0, count, STEP):
            ids = self.testrun_ids[offset:offset + STEP]
            for testrun in TestRun.objects.filter(id__in=ids).prefetch_related('attachments').all():
                export_testrun_files(testrun)

            if self.show_progress:
                print('.', end='', flush=True)
        print('[thread-%s] done' % self.thread_id)


def export_testrun_files(testrun):
    if not testrun.tests_file_storage:
        storage_save(testrun, testrun.tests_file_storage, 'tests_file', testrun.tests_file)

    if not testrun.metrics_file_storage:
        storage_save(testrun, testrun.metrics_file_storage, 'metrics_file', testrun.metrics_file)

    if not testrun.log_file_storage:
        storage_save(testrun, testrun.log_file_storage, 'log_file', testrun.log_file)

    for attachment in testrun.attachments.all():
        storage_save(attachment, attachment.storage, attachment.filename, attachment.data)


def storage_save(obj, storage_field, filename, content):
    content_bytes = content or ''
    if type(content_bytes) == str:
        content_bytes = content_bytes.encode()
    filename = '%s/%s/%s' % (obj.__class__.__name__.lower(), obj.pk, filename)
    storage_field.save(filename, ContentFile(content_bytes))


class Command(BaseCommand):

    help = """Migrate Attachment objects contents to files. Also
    migrate tests_file, metrics_file, log_file and metadata_file
    from TestRun object to files"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-progress',
            action='store_true',
            help='Prints out one dot every 1000 (one thousand) testruns processed'
        )

    def handle(self, *args, **options):
        show_progress = options['show_progress']

        null_storage_files = Q(tests_file_storage__isnull=True) | Q(metrics_file_storage__isnull=True) | Q(log_file_storage__isnull=True)
        testrun_ids = TestRun.objects.filter(null_storage_files).order_by('id').values_list('id', flat=True)

        if len(testrun_ids) == 0:
            print('Nothing to do!')
            return

        num_threads = multiprocessing.cpu_count() * 2
        chunk_size = math.floor(len(testrun_ids) / num_threads) + 1
        chunks = split_list(testrun_ids, chunk_size=chunk_size)

        threads = []
        for chunk in chunks:
            thread = TestRunFileExporterThread(len(threads), chunk, show_progress=show_progress)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        # Check that everything worked as expected
        count = TestRun.objects.filter(null_storage_files).count()
        if count > 0:
            print('Something went wrong! %d test runs still do not have files exported' % count)
            return

        count = Attachment.objects.filter(storage__isnull=True).count()
        if count > 0:
            print('Something went wrong! %d attachments still do not have files exported' % count)
            return

        print('Done!')

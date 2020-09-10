from io import BytesIO, StringIO
from django.core.files import File
from django.core.management.base import BaseCommand

from squad.core.models import Attachment, TestRun


class Command(BaseCommand):

    help = """Migrate Attachment objects contents to files. Also
    migrate tests_file, metrics_file, log_file and metadata_file
    from TestRun object to files"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-progress',
            action='store_true',
            help='Prints out one dot every 1000 (one thousand) attachments/testruns processed'
        )

    def handle(self, *args, **options):
        show_progress = options['show_progress']
        attachment_index = 0
        for attachment in Attachment.objects.all():
            if not attachment.storage:
                contents = BytesIO(bytes(attachment.data))
                contents_file = File(contents)
                storage_filename = "%s/%s/%s" % (
                    attachment.__class__.__name__.lower(),
                    attachment.id,
                    attachment.filename
                )
                attachment.storage.save(storage_filename, contents_file)
            attachment_index += 1
            if attachment_index % 1000 == 0 and show_progress:
                print('.', end='', flush=True)

        testrun_index = 0
        for testrun in TestRun.objects.all():
            if not testrun.tests_file_storage:
                tests_file_contents = StringIO(testrun.tests_file)
                tests_file = File(tests_file_contents)
                storage_filename = "testrun/%s/tests_file" % (testrun.id)
                testrun.tests_file_storage.save(storage_filename, tests_file)

            if not testrun.metrics_file_storage:
                metrics_file_contents = StringIO(testrun.metrics_file)
                metrics_file = File(metrics_file_contents)
                storage_filename = "testrun/%s/metrics_file" % (testrun.id)
                testrun.metrics_file_storage.save(storage_filename, metrics_file)

            if not testrun.log_file_storage:
                log_file_contents = StringIO(testrun.log_file)
                log_file = File(log_file_contents)
                storage_filename = "testrun/%s/log_file" % (testrun.id)
                testrun.log_file_storage.save(storage_filename, log_file)

            testrun_index += 1
            if testrun_index % 1000 == 0 and show_progress:
                print('.', end='', flush=True)

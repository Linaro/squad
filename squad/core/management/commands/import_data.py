from glob import glob
import json
import os
import re
import sys
from django.core.management.base import BaseCommand


from squad.core.models import Group
from squad.core.tasks import ReceiveTestRun


def build_key(path):
    name = os.path.basename(path)
    if re.match('^[0-9]+$', name):
        return int(name)
    elif re.match('^[0-9a-f]+$', name):
        return int(name, 16)
    else:
        return 0


class Command(BaseCommand):

    help = """Import data from DIRECTORY into PROJECT. See
    squad/core/management/commands/import_data.rst for documentation on the
    expected format"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', '-d',
            action='store_true',
            dest='dry_run',
            help='dry run (i.e. don\'t really do the importing)',
        )

        parser.add_argument(
            '--silent', '-s',
            action='store_true',
            dest='silent',
            help='operate silently (i.e. don\'t output anything)',
        )

        parser.add_argument(
            'PROJECT',
            help='Target project, on the form $group/$project',
        )

        parser.add_argument(
            'DIRECTORY',
            help='Input directory with the files to import',
        )

    def handle(self, *args, **options):
        self.options = options

        if not self.options['dry_run']:
            group_id, project_id = options['PROJECT'].split('/')
            self.group, _ = Group.objects.get_or_create(slug=group_id)
            self.project, _ = self.group.projects.get_or_create(slug=project_id)
            self.receive_test_run = ReceiveTestRun(self.project)

        if not self.options['silent']:
            print()
            msg = "Importing project: %s" % options["DIRECTORY"]
            print(msg)
            print('-' * len(msg))
            print()

        builds = sorted(glob(os.path.join(options['DIRECTORY'], '*')), key=build_key)
        for directory in builds:
            self.import_build(directory)

    def import_build(self, directory):
        build_id = os.path.basename(directory)

        for envdir in glob(os.path.join(directory, '*')):
            self.import_environment(build_id, envdir)

    def import_environment(self, build_id, directory):
        environment_slug = os.path.basename(directory)

        for testrundir in glob(os.path.join(directory, '*')):
            self.import_testrun(build_id, environment_slug, testrundir)

    def import_testrun(self, build_id, environment_slug, directory):
        # mandatory
        metadata = open(os.path.join(directory, 'metadata.json')).read()

        try:
            metrics = open(os.path.join(directory, 'metrics.json')).read()
        except FileNotFoundError:
            metrics = None

        try:
            tests = open(os.path.join(directory, 'tests.json')).read()
        except FileNotFoundError:
            tests = None

        attachments = {}
        for f in glob(os.path.join(directory, '*')):
            name = os.path.basename(f)
            if name not in ['metrics.json', 'metadata.json', 'tests.json']:
                attachments[name] = open(f, 'rb').read()

        if not self.options['silent']:
            print("Importing test run: %s" % directory)
        if self.options['dry_run']:
            return
        self.receive_test_run(
            version=build_id,
            environment_slug=environment_slug,
            metadata_file=metadata,
            metrics_file=metrics,
            tests_file=tests,
            attachments=attachments,
        )

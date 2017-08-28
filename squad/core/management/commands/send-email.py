from django.core.management.base import BaseCommand
from squad.core.models import Group
from squad.core.notification import send_status_notification


class Command(BaseCommand):

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
            'BUILD',
            help='Build id (version)',
        )

    def handle(self, *args, **options):
        g, p = options['PROJECT'].split('/')

        group = Group.objects.get(slug=g)
        project = group.projects.get(slug=p)
        build = project.builds.get(version=options['BUILD'])
        send_status_notification(build.status)

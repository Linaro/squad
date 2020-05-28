import argparse
import logging

from datetime import timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from squad.core.models import Project, Build, ProjectStatus


logger = logging.getLogger()
environments_cache = {}


def valid_date(date):
    try:
        return datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        msg = "'{0}' is not a valid date.".format(
            date)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):

    help = """Compute project statuses and set the baseline field"""

    def add_arguments(self, parser):
        parser.add_argument('--project', help='Optionally, specify a project to compute, on the form $group/$project')
        parser.add_argument('--show-progress', action='store_true', help='Prints out one dot per build in stdout')
        parser.add_argument(
            '--start-date',
            dest="start_date",
            default=(datetime.now() - timedelta(days=180)),
            type=valid_date,
            help="Start date for project status updates (default: 6 months before current date, format: YYYY-MM-DD)."
        )
        parser.add_argument(
            '--end-date',
            dest="end_date",
            default=datetime.now(),
            type=valid_date,
            help="End date for project status updates (default: today, format: YYYY-MM-DD)."
        )

    def __progress__(self, show):
        if show:
            self.stdout.write(".", ending="")
            self.stdout._out.flush()

    def handle(self, *args, **options):
        start_date = timezone.make_aware(options['start_date'])
        end_date = timezone.make_aware(options['end_date'])
        project_name = options['project'] or False
        show_progress = options['show_progress']
        logger.info("Filtering builds from %s to %s" % (start_date, end_date))
        builds = Build.objects.filter(
            datetime__range=(start_date, end_date)
        )

        project = None
        if project_name:
            slugs = project_name.split('/')
            if len(slugs) != 2:
                logger.error('Project "%s" is malformed (should be group_slug/project_slug). Exiting...' % (project_name))
                return

            try:
                group_slug, project_slug = slugs
                project = Project.objects.get(group__slug=group_slug, slug=project_slug)
            except Project.DoesNotExist:
                logger.error('Project "%s" does not exist. Exiting...' % (project_name))
                return

            logger.info('Filtering builds from project "%s"' % (project_name))
            builds = builds.filter(project=project)

        logger.info('Computing metrics summary for %d builds' % (builds.count()))
        if show_progress:
            logger.info('Showing progress, one dot means one processed build')

        for build in builds.all():
            self.__progress__(show_progress)
            ProjectStatus.create_or_update(build)

        if show_progress:
            self.stdout.write("")
            self.stdout._out.flush()

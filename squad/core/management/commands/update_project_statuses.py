import argparse
import logging

from datetime import timedelta, datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from squad.core.models import ProjectStatus, Build


logger = logging.getLogger()


def valid_date(date):
    try:
        return datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        msg = "'{0}' is not a valid date.".format(
            date)
        raise argparse.ArgumentTypeError(msg)


class Command(BaseCommand):

    help = """Update project status records in order to fix a bug which compared current builds with the wrong ones."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--date-start',
            dest="date_start",
            default=(datetime.now() - timedelta(days=180)),
            type=valid_date,
            help="Start date for project status updates (default: 6 months before current date, format: YYYY-MM-DD)."
        )
        parser.add_argument(
            '--date-end',
            dest="date_end",
            default=datetime.now(),
            type=valid_date,
            help="End date for project status updates (default: today, format: YYYY-MM-DD)."
        )

    def handle(self, *args, **options):
        self.options = options

        builds = Build.objects.filter(
            datetime__range=(
                timezone.make_aware(self.options['date_start']),
                timezone.make_aware(self.options['date_end'])),
            status__finished=True
        )
        total = builds.count()

        logger.info("Updating ProjectStatus objects from builds...")
        logger.info("Total build count in selected date range: %s" % total)

        for index, build in enumerate(builds.iterator()):
            ProjectStatus.create_or_update(build)
            if index % 100 == 0:
                logger.info('Progress: {1:>2}%[{0:10}]'.format(
                    '#' * int((index + 1) * 10 / total),
                    int((index + 1) * 100 / total)))
        logger.info('Progress: {1:>2}%[{0:10}]'.format('#' * 10, 100))

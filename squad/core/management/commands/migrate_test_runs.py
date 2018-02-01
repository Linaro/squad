import sys
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction

from squad.core.models import Project, Build, Environment, Status, Test, Metric
from squad.core.tasks import UpdateProjectStatus


class Command(BaseCommand):

    help = """Move test runs identified by environment slug
    from one project to another. This action preserves
    datetime of the objects and statuses."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--old-project-slug',
            dest="old_project_slug",
            help="Slug of the project from which to migrate test runs"
        )
        parser.add_argument(
            '--new-project-slug',
            dest="new_project_slug",
            help="Slug of the project to which to migrate test runs"
        )
        parser.add_argument(
            '--env-slug',
            dest="env_slug",
            help="Slug of the environment to migrate to new project"
        )

    def handle(self, *args, **options):
        self.options = options

        if not self.options['old_project_slug']:
            print("ERROR: old_project_slug missing")
            sys.exit(1)

        if not self.options['new_project_slug']:
            print("ERROR: new_project_slug missing")
            sys.exit(1)

        if not self.options['env_slug']:
            print("ERROR: env_slug missing")
            sys.exit(1)

        old_project = None
        new_project = None
        env = None
        try:
            old_project = Project.objects.get(slug=self.options['old_project_slug'])
        except ObjectDoesNotExist:
            print("Project: %s not found. Exiting" % self.options['old_project_slug'])
            sys.exit(0)
        try:
            new_project = Project.objects.get(slug=self.options['new_project_slug'])
        except ObjectDoesNotExist:
            print("Project: %s not found. Exiting" % self.options['new_project_slug'])
            sys.exit(0)
        try:
            env = Environment.objects.get(project=old_project, slug=self.options['env_slug'])
        except ObjectDoesNotExist:
            print("Environment: %s not found. Exiting" % self.options['env_slug'])
            sys.exit(0)
        print("Migrating testruns from project %s to %s" % (old_project.slug, new_project.slug))
        print("All test runs with environment name: %s will be migrated" % env.slug)
        self.__handle__(old_project, new_project, env)

    @transaction.atomic
    def __handle__(self, old_project, new_project, env):
        for build in old_project.builds.all():
            if build.test_runs.filter(environment=env):
                print("moving build: %s" % build)
                new_build, _ = Build.objects.get_or_create(
                    version=build.version,
                    datetime=build.datetime,
                    project=new_project,
                    created_at=build.created_at)
                for testrun in build.test_runs.filter(environment=env):
                    testrun.build = new_build
                    testrun.save()
                    testrun.environment.project = new_project
                    testrun.environment.save()
                    for testjob in testrun.test_jobs.all():
                        testjob.target = new_project
                        testjob.save()
                    UpdateProjectStatus()(testrun)
                new_build.status.created_at = build.status.created_at
                new_build.status.last_updated = build.status.last_updated
                new_build.status.save()
            else:
                print("No matching test runs found in build: %s" % build)

        env.project = new_project
        env.save()

        for suite in old_project.suites.all():
            new_suite, _ = new_project.suites.get_or_create(
                slug=suite.slug,
                defaults={'name': suite.name}
            )
            for model in [Status, Test, Metric]:
                model.objects.filter(
                    suite=suite,
                    test_run__build__project_id=new_project.id,
                ).update(suite=new_suite)

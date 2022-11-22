import logging
import requests

from squad.core.models import Group, SuiteMetadata
from squad.ci.models import TestJob
from django.core.management.base import BaseCommand


logger = logging.getLogger()

cache = {}


class Command(BaseCommand):
    help = """Create boot retroactive tests for TuxSuite backends"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            required=True,
            help="Project to fetch the data into (Format: foo/bar)",
        )

        parser.add_argument(
            "--days",
            required=True,
            help="How many days going backwards tests should be checked on TuxSuite. Maximum is 90 days",
        )

    def get_build_name(self, testjob):
        test_url = testjob.url
        if test_url not in cache:
            cache[test_url] = requests.get(test_url).json()

        build_ksuid = cache[test_url].get("waiting_for")
        if build_ksuid in [None, ""]:
            logger.warning(f"No 'waiting_for' in {test_url}: {cache[test_url]}")
            return None

        _, _, test_ksuid = testjob.backend.get_implementation().parse_job_id(testjob.job_id)
        build_url = test_url.replace(test_ksuid, build_ksuid).replace("tests", "builds")
        if build_url not in cache:
            cache[build_url] = requests.get(build_url).json()

        build_metadata = cache[build_url]

        if "toolchain" not in build_metadata or "kconfig" not in build_metadata:
            logger.warning(f"No 'toolchain' or 'kconfig' in {build_url}: {cache[build_url]}")
            return None

        return testjob.backend.get_implementation().generate_test_name(build_metadata)

    def get_boot_result(self, testjob):
        test_url = testjob.url
        if test_url not in cache:
            cache[test_url] = requests.get(test_url).json()

        return cache[test_url]["results"]["boot"]

    def handle(self, *args, **options):
        """
        Background

        TuxSuite backends run builds and tests. For tests, by default we didn't use to keep a boot
        test. This is being implemented now (date of this commit) so we needed a way to retractively
        add such boot tests.
        """

        group_slug, project_slug = options.get("project").split("/")
        group = Group.objects.get(slug=group_slug)
        project = group.projects.get(slug=project_slug)

        testjobs = TestJob.objects.filter(job_id__startswith="TEST", backend__implementation_type="tuxsuite", target=project).prefetch_related("backend")
        logger.info(f"Working on {testjobs.count()} testjobs")

        tests_created = 0
        tests_exsisting = 0
        bad_jobs = 0
        suite, created = project.suites.get_or_create(slug="boot")
        for testjob in testjobs:
            testrun = testjob.testrun
            if testrun is None:
                bad_jobs += 1
                continue

            print(".", end="")

            build_name = testrun.metadata.get("build_name")
            if build_name is None:
                build_name = self.get_build_name(testjob)

            if build_name is None:
                logger.info(f"Seems like Tuxsuite no longer keeps {testjob.url}, aborting now")
                break

            boot_test_name = build_name
            metadata, _ = SuiteMetadata.objects.get_or_create(kind="test", name=boot_test_name, suite="boot")

            if testrun.tests.filter(metadata=metadata).exists():
                print(":", end="")
                tests_exsisting += 1
                continue

            boot_result = self.get_boot_result(testjob)
            testrun.tests.create(
                build=testrun.build,
                environment=testrun.environment,
                metadata=metadata,
                result=(boot_result == "pass"),
                suite=suite,
            )

            tests_created += 1

        logger.info(f"Done: {tests_created} tests created, {tests_exsisting} tests exist already and {bad_jobs} jobs did not generate testruns")

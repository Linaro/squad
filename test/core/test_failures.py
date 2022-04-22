from django.test import TestCase
from squad.core.failures import failures_with_confidence
from squad.core.models import Build, Group, SuiteMetadata


def get_build_failures(build):
    return build.tests.filter(
        result=False,
    ).exclude(
        has_known_issues=True,
    ).only(
        'suite__slug', 'metadata__name', 'metadata__id',
    ).order_by(
        'suite__slug', 'metadata__name',
    ).distinct().values_list(
        'suite__slug', 'metadata__name', 'metadata__id', named=True,
    )


class FailuresWithConfidenceTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')

    def test_failures_with_confidence(self):
        env = self.project.environments.create(slug="env")
        suite = self.project.suites.create(slug="suite")
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test", kind="test")

        b1 = Build.objects.create(project=self.project, version='1.1')
        tr1 = b1.test_runs.create(environment=env)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata, result=True)

        b2 = Build.objects.create(project=self.project, version='1.2')
        tr2 = b2.test_runs.create(environment=env)
        tr2.tests.create(build=tr2.build, environment=tr2.environment, suite=suite, metadata=metadata, result=True)

        b3 = Build.objects.create(project=self.project, version='1.3')
        tr3 = b3.test_runs.create(environment=env)
        tr3.tests.create(build=tr3.build, environment=tr3.environment, suite=suite, metadata=metadata, result=False)

        f1 = failures_with_confidence(self.project, b1, get_build_failures(b1))
        self.assertEqual(len(f1), 0)

        f2 = failures_with_confidence(self.project, b2, get_build_failures(b2))
        self.assertEqual(len(f2), 0)

        f3 = failures_with_confidence(self.project, b3, get_build_failures(b3))
        self.assertEqual(len(f3), 1)

        test = f3.first()
        self.assertIsNotNone(test)
        self.assertIsNotNone(test.confidence)
        self.assertEqual(test.confidence.passes, 2)
        self.assertEqual(test.confidence.count, 2)
        self.assertEqual(test.confidence.score, 100)
        self.assertEqual(test.confidence.threshold, self.project.build_confidence_threshold)

    def test_failures_with_confidence_with_no_history(self):
        env = self.project.environments.create(slug="env")
        suite = self.project.suites.create(slug="suite")
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test", kind="test")

        b1 = Build.objects.create(project=self.project, version='1.1')
        tr1 = b1.test_runs.create(environment=env)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata, result=False)

        f1 = failures_with_confidence(self.project, b1, get_build_failures(b1))
        self.assertEqual(len(f1), 1)

        test = f1.first()
        self.assertIsNotNone(test)
        self.assertIsNotNone(test.confidence)
        self.assertEqual(test.confidence.passes, 0)
        self.assertEqual(test.confidence.count, 0)
        self.assertEqual(test.confidence.score, 0)
        self.assertEqual(test.confidence.threshold, self.project.build_confidence_threshold)

from django.test import TestCase
from squad.core.failures import FailuresWithConfidence
from squad.core.models import Build, Group, SuiteMetadata


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

        f1 = FailuresWithConfidence(self.project, b1)
        self.assertEqual(len(f1.failures()), 0)

        f2 = FailuresWithConfidence(self.project, b2)
        self.assertEqual(len(f2.failures()), 0)

        f3 = FailuresWithConfidence(self.project, b3)
        self.assertEqual(len(f3.failures()), 1)

        test = f3.failures().first()
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

        f1 = FailuresWithConfidence(self.project, b1)
        self.assertEqual(len(f1.failures()), 1)

        test = f1.failures().first()
        self.assertIsNotNone(test)
        self.assertIsNotNone(test.confidence)
        self.assertEqual(test.confidence.passes, 0)
        self.assertEqual(test.confidence.count, 0)
        self.assertEqual(test.confidence.score, 0)
        self.assertEqual(test.confidence.threshold, self.project.build_confidence_threshold)

    def test_failures_with_confidence_pagination(self):
        env = self.project.environments.create(slug="env")
        suite = self.project.suites.create(slug="suite")
        metadata1, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test1", kind="test")
        metadata2, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test2", kind="test")

        b1 = Build.objects.create(project=self.project, version='1.1')
        tr1 = b1.test_runs.create(environment=env)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata1, result=False)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata2, result=False)

        # default failures per page
        f = FailuresWithConfidence(self.project, b1)
        self.assertEqual(len(f.failures()), 2)

        # one failure per page
        fp1 = FailuresWithConfidence(self.project, b1, per_page=1, page=1)
        self.assertEqual(len(fp1.failures()), 1)

        fp2 = FailuresWithConfidence(self.project, b1, per_page=1, page=2)
        self.assertEqual(len(fp2.failures()), 1)

    def test_failures_with_confidence_search(self):
        env = self.project.environments.create(slug="env")
        suite = self.project.suites.create(slug="suite")
        metadata1, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test1", kind="test")
        metadata2, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name="test2", kind="test")

        b1 = Build.objects.create(project=self.project, version='1.1')
        tr1 = b1.test_runs.create(environment=env)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata1, result=False)
        tr1.tests.create(build=tr1.build, environment=tr1.environment, suite=suite, metadata=metadata2, result=False)

        f = FailuresWithConfidence(self.project, b1, search="test2")
        self.assertEqual(len(f.failures()), 1)

        test = f.failures().first()
        self.assertIsNotNone(test)
        self.assertEqual(test.full_name, "suite/test2")

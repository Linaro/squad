import json


from django.test import TestCase


from squad.core import models
from squad.core.comparison import TestComparison
from squad.core.tasks import ReceiveTestRun


def compare(b1, b2):
    return TestComparison.compare_builds(b1, b2)


class TestComparisonTest(TestCase):

    def receive_test_run(self, project, version, env, tests):
        receive = ReceiveTestRun(project)
        receive(version, env, tests_file=json.dumps(tests))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
        self.project1 = self.group.projects.create(slug='project1')
        self.project2 = self.group.projects.create(slug='project2')

        self.receive_test_run(self.project1, '0', 'myenv', {
            'z': 'pass',
        })

        self.receive_test_run(self.project1, '1', 'myenv', {
            'a': 'pass',
            'b': 'pass',
        })
        self.receive_test_run(self.project1, '1', 'myenv', {
            'c': 'fail',
            'd/e': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'a': 'fail',
            'b': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'c': 'pass',
            'd/e': 'pass',
        })

        self.receive_test_run(self.project1, '1', 'otherenv', {
            'a': 'pass',
            'b': 'pass',
        })
        self.receive_test_run(self.project1, '1', 'otherenv', {
            'c': 'fail',
            'd/e': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'a': 'fail',
            'b': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'c': 'pass',
            'd/e': 'pass',
        })

        self.build0 = self.project1.builds.first()
        self.build1 = self.project1.builds.last()
        self.build2 = self.project2.builds.last()

    def test_builds(self):
        comp = compare(self.build1, self.build2)
        self.assertEqual([self.build1, self.build2], comp.builds)

    def test_test_runs(self):
        comp = compare(self.build1, self.build2)

        self.assertEqual(['myenv', 'otherenv'], comp.environments[self.build1])
        self.assertEqual(['myenv', 'otherenv'], comp.environments[self.build2])

    def test_tests_are_sorted(self):
        comp = compare(self.build0, self.build1)
        self.assertEqual(['a', 'b', 'c', 'd/e', 'z'], list(comp.results.keys()))

    def test_test_results(self):
        comp = compare(self.build1, self.build2)

        self.assertEqual('pass', comp.results['a'][self.build1, 'otherenv'])
        self.assertEqual('fail', comp.results['c'][self.build1, 'otherenv'])

        self.assertEqual('fail', comp.results['a'][self.build2, 'otherenv'])
        self.assertEqual('pass', comp.results['b'][self.build2, 'otherenv'])

    def test_compare_projects(self):
        comp = TestComparison.compare_projects(self.project1, self.project2)
        self.assertEqual([self.build1, self.build2], comp.builds)

    def test_no_data(self):
        new_project = self.group.projects.create(slug='new')
        comp = TestComparison.compare_projects(new_project)
        self.assertFalse(comp.diff)
        self.assertEqual([], comp.builds)

    def test_diff(self):
        comparison = compare(self.build1, self.build2)
        diff = comparison.diff
        self.assertEqual(['a', 'c'], sorted(diff.keys()))

    def test_empty_diff(self):
        comparison = compare(self.build1, self.build1)  # same build → no diff
        self.assertFalse(comparison.diff)

    def test_empty_with_no_builds(self):
        new_project = self.group.projects.create(slug='new')
        comparison = TestComparison.compare_projects(new_project)
        self.assertFalse(comparison.diff)

    def test_regressions(self):
        """
        This test is using builds from different projects because the relevant
        test data is already prepared in setUp(), but usually regressions is
        only used when comparing subsequent builds from the same project.
        """
        comparison = TestComparison.compare_builds(self.build1, self.build2)
        regressions = comparison.regressions
        self.assertEqual(['a'], regressions['myenv'])
        self.assertEqual(['a'], regressions['otherenv'])

    def test_fixes(self):
        """
        This test is using builds from different projects because the relevant
        test data is already prepared in setUp(), but usually regressions is
        only used when comparing subsequent builds from the same project.
        """
        comparison = TestComparison.compare_builds(self.build1, self.build2)
        fixes = comparison.fixes
        self.assertEqual(['c'], fixes['myenv'])

    def test_failures(self):
        # Check if failures are ok
        comparison = TestComparison(self.build1)
        self.assertEqual(['c'], sorted([t.full_name for t in comparison.failures['myenv']]))

        self.receive_test_run(self.project1, '1', 'myenv', {'tests/another': 'fail'})
        comparison = TestComparison(self.build1)
        self.assertEqual(['c', 'tests/another'], sorted([t.full_name for t in comparison.failures['myenv']]))

    def test_regressions_no_previous_build(self):
        comparison = TestComparison.compare_builds(self.build1, None)
        regressions = comparison.regressions
        self.assertEqual({}, regressions)

    def test_fixes_no_previous_build(self):
        comparison = TestComparison.compare_builds(self.build1, None)
        fixes = comparison.fixes
        self.assertEqual({}, fixes)

    def test_regressions_no_regressions(self):
        # same build! so no regressions, by definition
        comparison = TestComparison.compare_builds(self.build1, self.build1)
        self.assertEqual({}, comparison.regressions)

    def test_fixes_no_fixes(self):
        # same build! so no fixes, by definition
        comparison = TestComparison.compare_builds(self.build1, self.build1)
        self.assertEqual({}, comparison.fixes)

    def test_xfail_fix(self):
        """
        This test is using builds from different projects because the relevant
        test data is already prepared in setUp(), but usually fixes is
        only used when comparing subsequent builds from the same project.
        """
        models.Test.objects.filter(test_run__build=self.build1, metadata__name='c').update(has_known_issues=True)
        comparison = TestComparison.compare_builds(self.build1, self.build2)
        fixes = comparison.fixes
        self.assertEqual(['c'], fixes['myenv'])

    def test_intermittent_xfail_is_not_a_fix(self):
        """
        This test is using builds from different projects because the relevant
        test data is already prepared in setUp(), but usually fixes is
        only used when comparing subsequent builds from the same project.
        """
        tests = models.Test.objects.filter(test_run__build=self.build1, metadata__name='c')
        tests.update(has_known_issues=True)
        issue = models.KnownIssue.objects.create(title='foo bar baz', intermittent=True)
        for test in tests:
            test.known_issues.add(issue)

        comparison = TestComparison.compare_builds(self.build1, self.build2)
        fixes = comparison.fixes
        self.assertEqual({}, fixes)

    def test_apply_transitions(self):
        """
        Test results scenario
                +---------------------+---------------------+
                |        buildA       |        buildB       |
                +------+------+-------+------+------+-------+
                | envA | envB | envC  | envA | envB | envC  |
        +-------+------+------+-------+------+------+-------+
        | testA | pass | fail | xfail | fail | pass | xfail |
        +-------+------+------+-------+------+------+-------+
        | testB | pass | skip | xfail | skip |      | xfail |
        +-------+------+------+-------+------+------+-------+
        | testC | pass | pass | pass  | pass | pass | pass  |
        +-------+------+------+-------+------+------+-------+
        """
        project = self.group.projects.create(slug='project3')
        self.receive_test_run(project, 'buildA', 'envA', {'testA': 'pass', 'testB': 'pass', 'testC': 'pass'})
        self.receive_test_run(project, 'buildA', 'envB', {'testA': 'fail', 'testB': 'skip', 'testC': 'pass'})
        self.receive_test_run(project, 'buildA', 'envC', {'testA': 'xfail', 'testB': 'xfail', 'testC': 'pass'})

        self.receive_test_run(project, 'buildB', 'envA', {'testA': 'fail', 'testB': 'skip', 'testC': 'pass'})
        self.receive_test_run(project, 'buildB', 'envB', {'testA': 'pass', 'testC': 'pass'})
        self.receive_test_run(project, 'buildB', 'envC', {'testA': 'xfail', 'testB': 'xfail', 'testC': 'pass'})

        buildA = project.builds.filter(version='buildA').get()
        buildB = project.builds.filter(version='buildB').get()

        comparison = TestComparison.compare_builds(buildA, buildB)
        self.assertEqual({'envB': ['testA']}, comparison.fixes)
        self.assertEqual({'envA': ['testA']}, comparison.regressions)
        self.assertEqual({'envA', 'envB', 'envC'}, comparison.all_environments)
        self.assertEqual(3, len(comparison.results))

        transitions = [('pass', 'fail'), ('skip', 'n/a')]
        comparison.apply_transitions(transitions)

        """
        Test results after transitions are applied
                +-------------+-------------+
                |    buildA   |   buildB    |
                +------+------+------+------+
                | envA | envB | envA | envB |
        +-------+------+------+------+------+
        | testA | pass | fail | fail | pass |
        +-------+------+------+------+------+
        | testB | pass | skip | skip |      |
        +-------+------+------+------+------+
        """

        self.assertEqual({'envB': ['testA']}, comparison.fixes)
        self.assertEqual({'envA': ['testA']}, comparison.regressions)
        self.assertEqual({'envA', 'envB'}, comparison.all_environments)
        self.assertEqual(2, len(comparison.results))
        self.assertEqual(None, comparison.results['testB'].get((buildB, 'envB')))

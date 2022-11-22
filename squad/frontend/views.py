import json
import mimetypes

from django.db.models import Case, When, Prefetch, Max
from django.core.paginator import Paginator, EmptyPage
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect, reverse

from squad.ci.models import TestJob
from squad.core.models import Group, Metric, ProjectStatus, Status, MetricThreshold, KnownIssue, Test
from squad.core.models import Build, Subscription, TestRun, SuiteMetadata
from squad.core.queries import get_metric_data, test_confidence
from squad.frontend.queries import get_metrics_list
from squad.frontend.utils import file_type, alphanum_sort
from squad.http import auth
from collections import OrderedDict


class BuildDeleted(Http404):

    def __init__(self, date, days):
        self.display_message = True
        msg = 'This build has been deleted on %s. ' % date
        msg += 'Builds in this project are usually deleted after %d days.' % days
        super(BuildDeleted, self).__init__(msg)


def get_build(project, version):
    if version == 'latest-finished':
        status = ProjectStatus.objects.prefetch_related('build').filter(
            build__project=project,
            finished=True,
        ).order_by('build__datetime').last()
        if status is None:
            raise Http404()
        build = status.build
    else:
        try:
            build = project.builds.get(
                version=version
            )
        except Build.DoesNotExist:
            placeholder = get_object_or_404(
                project.build_placeholders,
                version=version
            )
            deleted = placeholder.build_deleted_at
            days = project.data_retention_days
            raise BuildDeleted(deleted, days)
    return build


def home(request):

    ordering = request.GET.get('order')
    if ordering not in ['by_name', 'last_updated']:
        ordering = 'last_updated'

    if ordering == 'last_updated':
        all_groups = list(Group.objects.accessible_to(request.user).annotate(group_datetime=Max('projects__datetime')))
        for g in all_groups:
            g.timestamp = g.group_datetime.timestamp() if g.group_datetime else 0
        all_groups.sort(key=lambda g: g.timestamp, reverse=True)
    else:
        all_groups = Group.objects.accessible_to(request.user)

    user_spaces = [g for g in all_groups if g.slug.startswith('~')]
    all_groups = [g for g in all_groups if not g.slug.startswith('~')]

    context = {
        'all_groups': all_groups,
        'user_spaces': user_spaces,
    }
    return render(request, 'squad/index.jinja2', context)


def group_home(request, group_slug):
    group = get_object_or_404(Group, slug=group_slug)

    projects_queryset = group.projects.accessible_to(request.user)
    projects_queryset = projects_queryset.annotate(latest_build_id=Max('builds__id'))

    if request.user.is_authenticated:
        projects_queryset = projects_queryset.prefetch_related(Prefetch('subscriptions', queryset=Subscription.objects.filter(user=request.user), to_attr='user_subscriptions'))

    order_by = request.GET.get('order', 'last_updated')
    if group.get_setting('SORT_PROJECTS_BY_NAME'):
        order_by = 'by_name'

    elif order_by == 'last_updated':
        projects_queryset = projects_queryset.order_by('-datetime')

    display_all_projects = request.GET.get('all_projects') is not None
    num_projects = group.get_setting('DEFAULT_PROJECT_COUNT')
    if display_all_projects or num_projects is None:
        display_all_projects = True
        projects = projects_queryset.all()
    else:
        display_all_projects = projects_queryset.count() <= num_projects
        projects = projects_queryset.all()[:num_projects]

    has_archived_projects = False
    latest_build_ids = {}
    projects_count = 0
    for project in projects:
        if project.latest_build_id:
            latest_build_ids[project.latest_build_id] = project
        else:
            project.latest_build = None

        if not has_archived_projects and project.is_archived:
            has_archived_projects = True

        projects_count += 1

    for build in Build.objects.filter(id__in=latest_build_ids.keys()).prefetch_related('status').only('id'):
        latest_build_ids[build.id].latest_build = build

    if len(projects) == 0 and not group.can_submit_results(request.user):
        raise Http404()

    context = {
        'display_all_projects': display_all_projects,
        'group': group,
        'order_by': order_by,
        'projects': alphanum_sort(projects, 'name') if order_by == 'by_name' else projects,
        'has_archived_projects': has_archived_projects,
    }
    response = render(request, 'squad/group.jinja2', context)
    return response


def __get_builds_with_status__(project, limit=None):
    builds = project.builds.prefetch_related('status').order_by('-datetime')
    if limit:
        return builds[:limit]
    return builds


@auth
def project_home(request, group_slug, project_slug):
    project = request.project
    project.user_subscriptions = None

    if request.user.is_authenticated:
        project.user_subscriptions = project.subscriptions.filter(user=request.user)

    builds = [b for b in __get_builds_with_status__(project, 11)]
    last_build = len(builds) and builds[0] or None

    metadata = last_build and sorted(last_build.important_metadata.items()) or ()
    context = {
        'project': project,
        'builds': builds,
        'last_build': last_build,
        'metadata': metadata,
    }
    return render(request, 'squad/project.jinja2', context)


@auth
def builds(request, group_slug, project_slug):
    project = request.project

    all_builds = __get_builds_with_status__(project)
    paginator = Paginator(all_builds, 25)
    page = request.GET.get('page', 1)
    try:
        builds = paginator.page(page)

        context = {
            'project': project,
            'builds': builds,
        }
        return render(request, 'squad/builds.jinja2', context)
    except EmptyPage:
        raise Http404()


class TestResultTable(object):

    class Cell(object):

        def __init__(self):
            self.has_failures = False
            self.has_known_failures = False
            self.statuses = []

        @property
        def has_data(self):
            return len(self.statuses) > 0

    def __init__(self):
        self.data = OrderedDict()
        self.environments = []
        self.test_runs = set()

    def add_status(self, status):
        suite = status.suite
        environment = status.environment
        if environment not in self.environments:
            self.environments.append(environment)
        if suite not in self.data:
            self.data[suite] = OrderedDict()
        if environment not in self.data[suite]:
            self.data[suite][environment] = TestResultTable.Cell()

        entry = self.data[suite][environment]
        if status.tests_fail > 0:
            entry.has_failures = True
        if status.tests_xfail > 0:
            entry.has_known_failures = True
        entry.statuses.append(status)
        self.test_runs.add(status.test_run)


def __rearrange_test_results__(results_layout, test_results):
    if results_layout == 'envbox':
        for e in test_results.environments:
            e.suites = []
            e.status = Status()

        for suite, results in test_results.data.items():
            for env in results.keys():
                statuses = [s for s in results[env].statuses if s.environment.id == env.id]
                for status in statuses:
                    env.status.tests_pass += status.tests_pass
                    env.status.tests_skip += status.tests_skip
                    env.status.tests_fail += status.tests_fail
                    env.status.tests_xfail += status.tests_xfail
                env.suites.append((suite, statuses))

    if results_layout == 'suitebox':
        test_results.suites = test_results.data.keys()
        for suite in test_results.suites:
            envs = []
            suite.status = Status()
            for environment, cell in test_results.data[suite].items():
                envs.append((environment, cell.statuses))
                for status in cell.statuses:
                    suite.status.tests_pass += status.tests_pass
                    suite.status.tests_skip += status.tests_skip
                    suite.status.tests_fail += status.tests_fail
                    suite.status.tests_xfail += status.tests_xfail
            suite.environments = sorted(envs, key=lambda e: e[0].slug)


def __testjobs_progress__(build, request):

    per_environment = request.GET.get('testjobs_progress_per_environments', None)
    testjobs_progress = {}
    if per_environment is None:
        summary = build.test_jobs_summary()

        progress_complete = summary.get('Complete', 0)
        progress_failed = summary.get('Incomplete', 0) + summary.get('Canceled', 0)
        progress_running = summary.get('Running', 0)
        progress_none = summary.get(None, 0) + summary.get('Submitted', 0)
        total = progress_complete + progress_failed + progress_running + progress_none

        testjobs_progress['total'] = total
        testjobs_progress['finished'] = progress_complete + progress_failed

        # Avoid division by zero without interfering with computations
        if total == 0:
            total = 1

        testjobs_progress['percentage'] = int(((progress_complete + progress_failed) / total) * 100)

        testjobs_progress['progress'] = {}
        testjobs_progress['progress']['complete'] = {'total': progress_complete, 'width': (progress_complete / total) * 100, 'query_string': 'job_status=Complete'}
        testjobs_progress['progress']['failed'] = {'total': progress_failed, 'width': (progress_failed / total) * 100, 'query_string': 'job_status=Incomplete'}
        testjobs_progress['progress']['running'] = {'total': progress_running, 'width': (progress_running / total) * 100, 'query_string': 'job_status=Running'}
        testjobs_progress['progress']['none'] = {'total': progress_none, 'width': (progress_none / total) * 100, 'query_string': 'submitted=true&fetched=false'}
    else:
        env_summary = build.test_jobs_summary(per_environment=True)
        testjobs_progress['total'] = 0
        testjobs_progress['finished'] = 0
        testjobs_progress['percentage'] = 0
        testjobs_progress['envs'] = {}
        max_jobs = -1

        for env, summary in env_summary.items():
            progress_complete = summary.get('Complete', 0)
            progress_failed = summary.get('Incomplete', 0) + summary.get('Canceled', 0)
            progress_running = summary.get('Running', 0)
            progress_none = summary.get(None, 0) + summary.get('Submitted', 0)
            total = progress_complete + progress_failed + progress_running + progress_none

            if total > max_jobs:
                max_jobs = total

            env_querystring = '&environment=%s' % env

            testjobs_progress['envs'][env] = {}
            testjobs_progress['envs'][env]['total'] = total
            testjobs_progress['envs'][env]['finished'] = progress_complete + progress_failed

            # Avoid division by zero without interfering with computations
            if total == 0:
                total = 1

            testjobs_progress['envs'][env]['percentage'] = int((testjobs_progress['envs'][env]['finished'] / total) * 100)

            testjobs_progress['envs'][env]['progress'] = {}
            testjobs_progress['envs'][env]['progress']['complete'] = {'total': progress_complete, 'width': (progress_complete / total) * 100, 'query_string': 'job_status=Complete' + env_querystring}
            testjobs_progress['envs'][env]['progress']['failed'] = {'total': progress_failed, 'width': (progress_failed / total) * 100, 'query_string': 'job_status=Incomplete' + env_querystring}
            testjobs_progress['envs'][env]['progress']['running'] = {'total': progress_running, 'width': (progress_running / total) * 100, 'query_string': 'job_status=Running' + env_querystring}
            testjobs_progress['envs'][env]['progress']['none'] = {'total': progress_none, 'width': (progress_none / total) * 100, 'query_string': 'submitted=true&fetched=false' + env_querystring}

            # Compute overall summary
            testjobs_progress['total'] += testjobs_progress['envs'][env]['total']
            testjobs_progress['finished'] += testjobs_progress['envs'][env]['finished']

        # Avoid division by zero without interfering with computations
        if max_jobs == 0:
            max_jobs = 1

        # Compute shrinking factor for each progress for each environment
        for env in testjobs_progress['envs'].keys():

            shrink_factor = testjobs_progress['envs'][env]['total'] / max_jobs
            testjobs_progress['envs'][env]['shrink_factor'] = shrink_factor
            for progress in ['complete', 'failed', 'running', 'none']:
                testjobs_progress['envs'][env]['progress'][progress]['width'] *= shrink_factor

        # Compute the overall percentage
        testjobs_progress['percentage'] = int((testjobs_progress['finished'] / testjobs_progress['total']) * 100) if testjobs_progress['total'] > 0 else 0
    return testjobs_progress


@auth
def build(request, group_slug, project_slug, version):
    project = request.project
    build = get_build(project, version)

    failures_only = request.GET.get('failures_only', 'true')
    if failures_only not in ['true', 'false']:
        failures_only = 'true'

    queryset = Status.objects.filter(
        test_run__build=build,
    )

    if failures_only == 'true':
        queryset = queryset.filter(tests_fail__gt=0)

    __statuses__ = queryset.prefetch_related(
        'suite',
        Prefetch('test_run', queryset=TestRun.objects.prefetch_related('environment', 'attachments').all())
    ).order_by('-tests_fail', 'suite__slug', '-test_run__environment__slug')

    test_results = TestResultTable()
    for status in __statuses__:
        if status.suite:
            test_results.add_status(status)

    test_results.environments = sorted(test_results.environments, key=lambda e: e.slug)

    results_layout = request.GET.get('results_layout')
    if results_layout not in ['table', 'envbox', 'suitebox']:
        results_layout = 'suitebox'

    __rearrange_test_results__(results_layout, test_results)

    testjobs_progress = __testjobs_progress__(build, request)

    context = {
        'project': project,
        'build': build,
        'test_results': test_results,
        'results_layout': results_layout,
        'metadata': sorted(build.important_metadata.items()),
        'has_extra_metadata': build.has_extra_metadata,
        'failures_only': failures_only,
        'testjobs_progress': testjobs_progress,
    }
    return render(request, 'squad/build.jinja2', context)


@auth
def build_api(request, group_slug, project_slug, version):
    project = request.project
    build = get_build(project, version)
    return redirect(reverse('build-detail', args=[build.id]))


@auth
def build_metadata(request, group_slug, project_slug, version):
    project = request.project

    build = get_build(project, version)
    build.prefetch('test_runs')

    context = {
        'project': project,
        'build': build,
        'metadata': sorted(build.metadata.items()),
    }
    return render(request, 'squad/build_metadata.jinja2', context)


@auth
def build_callbacks(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    build = get_build(project, version)

    context = {
        'project': project,
        'build': build,
    }
    return render(request, 'squad/build_callbacks.jinja2', context)


@auth
def build_settings(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    build = get_build(project, version)

    context = {
        'project': project,
        'build': build,
    }
    return render(request, 'squad/build_settings.jinja2', context)


def __test_run_suite_context__(request, group_slug, project_slug, build_version, testrun, suite_slug):
    project = request.project
    build = get_build(project, build_version)

    test_run = get_object_or_404(build.test_runs, pk=testrun)
    suite = get_object_or_404(project.suites, slug=suite_slug.replace('$', '/'))
    status = get_object_or_404(test_run.status, suite=suite)
    context = {
        'project': project,
        'build': build,
        'test_run': test_run,
        'metadata': sorted(test_run.metadata.items()),
        'suite': suite,
        'status': status,
    }
    return context


@auth
def test_run_suite_tests(request, group_slug, project_slug, build_version, testrun, suite_slug):
    context = __test_run_suite_context__(
        request,
        group_slug,
        project_slug,
        build_version,
        testrun,
        suite_slug
    )

    all_tests = context['status'].tests.prefetch_related(
        'metadata',
        'known_issues',
        'suite__metadata'
    ).order_by(Case(When(result=False, then=0), When(result=True, then=2), default=1), 'metadata__name')

    paginator = Paginator(all_tests, 100)
    page = request.GET.get('page', '1')
    context['tests'] = paginator.page(page)

    return render(request, 'squad/test_run_suite_tests.jinja2', context)


@auth
def test_run_suite_test_details(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    context = __test_run_suite_context__(
        request,
        group_slug,
        project_slug,
        build_version,
        testrun,
        suite_slug
    )
    test_name = test_name.replace("$", "/")
    suite_slug = suite_slug.replace("$", "/")
    metadata = get_object_or_404(SuiteMetadata, kind='test', suite=suite_slug, name=test_name)
    tests = Test.objects.filter(suite=context['suite'], metadata=metadata, build=context['build'], environment=context['test_run'].environment)
    if len(tests) == 0:
        raise Http404()

    # There's more then one test that meets the criteria, this usually
    # means resubmitted job.
    if len(tests) > 1:
        # Calculate the most common status and confidence score.
        status, confidence_score = test_confidence(tests.first())
        # Take the first test with the most common status as the relevant
        # one.
        for t in tests:
            if t.status == status:
                test = t
        if not test:
            # Something went wrong, we're supposed to find a test by now.
            raise Http404()
        else:
            test.confidence_score = confidence_score
    else:
        test = tests.first()

    attachments = [
        (f['filename'], file_type(f['filename']), f['length'])
        for f in context['test_run'].attachments.values('filename', 'length')
    ]

    context.update({'test': test, 'attachments': attachments})
    return render(request, 'squad/test_run_suite_test_details.jinja2', context)


@auth
def test_run_suite_metrics(request, group_slug, project_slug, build_version, testrun, suite_slug):
    context = __test_run_suite_context__(
        request,
        group_slug,
        project_slug,
        build_version,
        testrun,
        suite_slug
    )
    all_metrics = context['status'].metrics.prefetch_related(
        'metadata',
        'suite__metadata'
    ).order_by('metadata__name')

    paginator = Paginator(all_metrics, 100)
    page = request.GET.get('page', '1')
    context['metrics'] = paginator.page(page)

    return render(request, 'squad/test_run_suite_metrics.jinja2', context)


def __download__(filename, data, content_type=None):
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'
    response = HttpResponse(data, content_type=content_type)
    return response


@auth
def test_details_log(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)

    if not test_run.log_file or len(test_run.log_file) == 0:
        raise Http404("No log file available for this test run")

    return HttpResponse(test_run.log_file, content_type="text/plain")


@auth
def test_details_tests(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    group = request.group
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)

    filename = '%s_%s_%s_%s_tests.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.tests_file)


@auth
def test_details_metrics(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    group = request.group
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)

    filename = '%s_%s_%s_%s_metrics.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metrics_file)


@auth
def test_details_metadata(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    group = request.group
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)

    filename = '%s_%s_%s_%s_metadata.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metadata_file)


@auth
def attachment(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name, filename):
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)
    attachment = get_object_or_404(test_run.attachments, filename=filename)
    return __download__(attachment.filename, bytes(attachment.data), attachment.mimetype)


@auth
def build_attachment(request, group_slug, project_slug, build_version, testrun, filename):
    return attachment(request, group_slug, project_slug, build_version, testrun, None, None, filename)


@auth
def metrics(request, group_slug, project_slug):
    project = request.project
    env_qs = project.environments.order_by('id').all()
    environments = [{"name": e.slug} for e in env_qs]
    metrics = get_metrics_list(project)

    data = get_metric_data(
        project,
        request.GET.getlist('metric'),
        env_qs.filter(slug__in=request.GET.getlist('environment'))
    )

    thresholds = []
    for t in MetricThreshold.objects.filter(environment__in=env_qs, value__isnull=False).only('name', 'value'):
        thresholds.append({'name': t.name, 'value': t.value})

    context = {
        "project": project,
        "environments": environments,
        "metrics": metrics,
        "thresholds": thresholds,
        "data": data,
    }
    return render(request, 'squad/metrics.jinja2', context)


class TestKnownIssues(object):

    def __init__(self, project, search, page=1, per_page=50):
        tests_issues = OrderedDict()
        self.project = project
        env_qs = project.environments.all().prefetch_related(Prefetch('knownissue_set', queryset=KnownIssue.objects.filter(test_name__icontains=search))).order_by()
        self.environments = [e.slug for e in env_qs]
        testnames = set()
        for env in env_qs:
            issues = env.knownissue_set.all()
            for issue in issues:
                testnames.add(issue.test_name)
                tests_issues.setdefault(issue.test_name, {})
                tests_issues[issue.test_name].update({env.slug: json.dumps({"url": issue.url,
                                                                            "notes": issue.notes,
                                                                            "intermittent": issue.intermittent,
                                                                            "active": issue.active})})
        self.paginator = Paginator(sorted([t for t in testnames]), per_page)
        self.number = page
        self.results = {x: tests_issues[x] for x in self.paginator.page(page).object_list}


@auth
def known_issues(request, group_slug, project_slug):
    project = request.project
    search = request.GET.get('search', '')
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    context = {
        "project": project,
        "search": search,
        "results": TestKnownIssues(project, search, page=page, per_page=50)
    }
    return render(request, 'squad/knownissues.jinja2', context)


@auth
@login_required
def toggle_outlier_metric(request, group_slug, project_slug, metric_id):

    try:
        metric = Metric.objects.select_related("environment").get(
            pk=metric_id)
    except Metric.DoesNotExist:
        raise Http404("Metric does not exist")

    metric.is_outlier = not metric.is_outlier
    metric.save()
    return HttpResponse(
        json.dumps(
            {"id": metric.id,
             "environment": metric.environment.slug}),
        content_type='application/json')


def test_job(request, testjob_id):
    testjob = get_object_or_404(TestJob, pk=testjob_id)
    if testjob.url is not None:
        # redirect to target executor
        return redirect(testjob.url)
    else:
        # display some description page
        context = {
            'testjob': testjob
        }
        return render(request, 'squad/testjob.jinja2', context)

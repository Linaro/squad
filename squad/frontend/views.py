import json
import mimetypes
import svgwrite

from django.db.models import Case, When
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect

from squad.ci.models import TestJob
from squad.core.models import Group, Metric, ProjectStatus, Status, MetricThreshold
from squad.core.models import Build
from squad.core.queries import get_metric_data
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
    context = {
        'groups': Group.objects.accessible_to(request.user),
    }
    return render(request, 'squad/index.jinja2', context)


def group_home(request, group_slug):
    group = get_object_or_404(Group, slug=group_slug)
    projects = alphanum_sort(group.projects.accessible_to(request.user), 'name')
    archived_projects = [p for p in projects if p.is_archived]
    context = {
        'group': group,
        'projects': projects,
        'has_archived_projects': len(archived_projects) > 0,
    }
    return render(request, 'squad/group.jinja2', context)


def __get_statuses__(project, limit=None):
    statuses = ProjectStatus.objects.filter(
        build__project=project
    ).prefetch_related(
        'build',
        'build__project'
    ).order_by('-build__datetime')
    if limit:
        statuses = statuses[:limit]
    return statuses


@auth
def project_home(request, group_slug, project_slug):
    project = request.project

    statuses = __get_statuses__(project, 11)
    last_status = statuses.first()
    last_build = last_status and last_status.build

    metadata = last_build and sorted(last_build.important_metadata.items()) or ()
    context = {
        'project': project,
        'statuses': statuses,
        'last_build': last_build,
        'metadata': metadata,
    }
    return render(request, 'squad/project.jinja2', context)


def __produce_badge(title_text, status, style=None):
    badge_text = "no results found"
    if status:
        badge_text = "pass: %s, fail: %s, xfail: %s, skip: %s" % \
            (status.tests_pass, status.tests_fail, status.tests_xfail, status.tests_skip)

    badge_colour = "#999"

    pass_rate = -1
    if status and status.tests_total:
        pass_rate = 100 * float(status.tests_pass) / float(status.tests_total)
        badge_colour = "#f0ad4e"
        if status.tests_fail == 0:
            badge_colour = "#5cb85c"
        if status.tests_pass == 0:
            badge_colour = "#d9534f"

    if style is not None:
        if style == 'passrate' and pass_rate != -1:
            badge_text = "%.2f%%" % (pass_rate)
        elif style == 'metrics' and status is not None and status.has_metrics:
            badge_text = str(status.metrics_summary)
            badge_colour = "#5cb85c"

    font_size = 110
    character_width = font_size / 2
    padding_width = character_width
    title_width = len(title_text) * character_width + 2 * padding_width
    title_x = title_width / 2 + padding_width
    badge_width = len(badge_text) * character_width + 2 * padding_width
    badge_x = badge_width / 2 + 3 * padding_width + title_width
    total_width = (title_width + badge_width + 4 * padding_width) / 10

    dwg = svgwrite.Drawing("test_badge.svg", (total_width, 20))
    a = dwg.add(dwg.clipPath())
    a.add(dwg.rect(rx=3, size=(total_width, 20), fill="#fff"))
    b = dwg.add(dwg.linearGradient(end=(0, 1), id="b"))
    b.add_stop_color(0, "#bbb", 0.1)
    b.add_stop_color(1, None, 0.1)
    g1 = dwg.add(dwg.g(clip_path=a.get_funciri()))
    g1.add(
        dwg.path(
            fill="#555",
            d=['M0', '0h', '%sv' % ((2 * padding_width + title_width) / 10), '20H', '0z']))
    g1.add(
        dwg.path(
            fill=badge_colour,
            d=['M%s' % ((2 * padding_width + title_width) / 10), '0h', '%sv' % ((2 * padding_width + badge_width) / 10), '20H', '%sz' % ((2 * padding_width + title_width) / 10)]))
    g1.add(
        dwg.path(
            fill=b.get_funciri(),
            d=['M0', '0h', '%sv' % total_width, '20H', '0z']))

    g2 = dwg.add(dwg.g(fill="#fff", text_anchor="middle", font_family="monospace", font_size=font_size))
    g2.add(dwg.text(title_text, x=[title_x], y=[150], fill="#010101", fill_opacity=".3", transform="scale(.1)", textLength=title_width))
    g2.add(dwg.text(title_text, x=[title_x], y=[140], transform="scale(.1)", textLength=title_width))
    g2.add(dwg.text(badge_text, x=[badge_x], y=[150], fill="#010101", fill_opacity=".3", transform="scale(.1)", textLength=badge_width))
    g2.add(dwg.text(badge_text, x=[badge_x], y=[140], transform="scale(.1)", textLength=badge_width))
    badge = dwg.tostring()

    return HttpResponse(badge, content_type="image/svg+xml")


def __badge_style(request):
    style = None
    if request.GET:
        if 'passrate' in request.GET.keys():
            style = 'passrate'
        elif 'metrics' in request.GET.keys():
            style = 'metrics'
    return style


@auth
def project_badge(request, group_slug, project_slug):
    project = request.project

    status = ProjectStatus.objects.filter(
        build__project=project,
        finished=True
    ).order_by("-build__datetime").first()

    title_text = project.slug

    if request.GET and 'title' in request.GET.keys():
        title_text = request.GET['title']

    style = __badge_style(request)
    return __produce_badge(title_text, status, style)


@auth
def build_badge(request, group_slug, project_slug, version):
    project = request.project
    build = get_build(project, version)
    status = build.status

    title_text = build.version

    if request.GET and 'title' in request.GET.keys():
        title_text = request.GET['title']

    style = __badge_style(request)
    return __produce_badge(title_text, status, style)


@auth
def builds(request, group_slug, project_slug):
    project = request.project

    all_statuses = __get_statuses__(project)
    paginator = Paginator(all_statuses, 25)
    page = request.GET.get('page', 1)
    statuses = paginator.page(page)

    context = {
        'project': project,
        'statuses': statuses,
    }
    return render(request, 'squad/builds.jinja2', context)


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

        for suite, results in test_results.data.items():
            for env in results.keys():
                statuses = [s for s in results[env].statuses if s.environment.id == env.id]
                env.suites.append((suite, statuses))

    if results_layout == 'suitebox':
        test_results.suites = test_results.data.keys()
        for suite in test_results.suites:
            envs = []
            for environment, cell in test_results.data[suite].items():
                envs.append((environment, cell.statuses))
            suite.environments = sorted(envs, key=lambda e: e[0].slug)


@auth
def build(request, group_slug, project_slug, version):
    project = request.project
    build = get_build(project, version)
    build.prefetch('test_runs')

    failures_only = request.GET.get('failures_only', 'true')
    if failures_only not in ['true', 'false']:
        failures_only = 'true'

    queryset = Status.objects.filter(
        test_run__build=build,
        suite__isnull=False,
    )

    if failures_only == 'true':
        queryset = queryset.filter(tests_fail__gt=0)

    __statuses__ = queryset.prefetch_related(
        'suite',
        'test_run',
        'test_run__environment',
    ).order_by('-tests_fail', 'suite__slug', '-test_run__environment__slug')

    test_results = TestResultTable()
    for status in __statuses__:
        test_results.add_status(status)

    test_results.environments = sorted(test_results.environments, key=lambda e: e.slug)

    results_layout = request.GET.get('results_layout')
    if results_layout not in ['table', 'envbox', 'suitebox']:
        results_layout = 'envbox' if len(test_results.environments) > 8 else 'table'

    __rearrange_test_results__(results_layout, test_results)

    context = {
        'project': project,
        'build': build,
        'test_results': test_results,
        'results_layout': results_layout,
        'metadata': sorted(build.important_metadata.items()),
        'has_extra_metadata': build.has_extra_metadata,
        'failures_only': failures_only,
    }
    return render(request, 'squad/build.jinja2', context)


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
        'suite',
        'metadata',
        'known_issues',
        'suite__metadata'
    ).order_by(Case(When(result=False, then=0), When(result=True, then=2), default=1), 'name')

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
    test = get_object_or_404(context['test_run'].tests, suite=context['suite'], name=test_name)
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
        'suite',
        'metadata',
        'suite__metadata'
    ).order_by('name')

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
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@auth
def test_details_log(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)

    if not test_run.log_file:
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
    return __download__(attachment.filename, attachment.data)


@auth
def metrics(request, group_slug, project_slug):
    project = request.project
    env_qs = project.environments.order_by('id').all()
    environments = [{"name": e.slug} for e in env_qs]
    metrics = get_metrics_list(project)

    data = get_metric_data(
        project,
        request.GET.getlist('metric'),
        request.GET.getlist('environment')
    )

    context = {
        "project": project,
        "environments": environments,
        "metrics": metrics,
        "thresholds": list(MetricThreshold.objects.filter(
            environment__in=env_qs
        ).values('name', 'value')),
        "data": data,
    }
    return render(request, 'squad/metrics.jinja2', context)


@auth
@login_required
def toggle_outlier_metric(request, group_slug, project_slug, metric_id):

    try:
        metric = Metric.objects.select_related("test_run__environment").get(
            pk=metric_id)
    except Metric.DoesNotExist:
        raise Http404("Metric does not exist")

    metric.is_outlier = not metric.is_outlier
    metric.save()
    return HttpResponse(
        json.dumps(
            {"id": metric.id,
             "environment": metric.test_run.environment.slug}),
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

import svgwrite

from django.http import HttpResponse

from squad.core.models import ProjectStatus, Status
from squad.frontend.views import get_build
from squad.http import auth


def __produce_badge(title_text, status, style=None, hide_zeros=False):
    badge_text = "no results found"
    if status:
        s = status
        if not hide_zeros:
            badge_text = f"pass: {s.tests_pass}, fail: {s.tests_fail}, xfail: {s.tests_xfail}, skip: {s.tests_skip}"
        else:
            texts = []
            if s.tests_pass > 0:
                texts.append(f"pass: {s.tests_pass}")
            if s.tests_fail > 0:
                texts.append(f"fail: {s.tests_fail}")
            if s.tests_xfail > 0:
                texts.append(f"xfail: {s.tests_xfail}")
            if s.tests_skip > 0:
                texts.append(f"skip: {s.tests_skip}")

            badge_text = ", ".join(texts)

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
    suite = None
    environment = None
    hide_zeros = False

    if request.GET:
        if 'title' in request.GET:
            title_text = request.GET.get('title')
        suite = request.GET.get('suite')
        environment = request.GET.get('environment')
        hide_zeros = request.GET.get('hide_zeros') in ["1", "true"]

    if suite or environment:
        testruns = build.test_runs.all()
        if environment:
            testruns = testruns.filter(environment__slug=environment)

        statuses = Status.objects.filter(test_run__in=testruns)
        if suite:
            statuses = statuses.filter(suite__slug=suite)

        # Compute status with suite and environment filters
        has_metrics = []
        metrics_summary = []
        status.tests_pass = status.tests_pass = status.tests_fail = status.tests_xfail = status.tests_skip = 0
        status.metrics_summary = 0.0
        for s in statuses.all():
            has_metrics.append(s.has_metrics)
            status.tests_pass += s.tests_pass
            status.tests_fail += s.tests_fail
            status.tests_xfail += s.tests_xfail
            status.tests_skip += s.tests_skip
            metrics_summary.append(s.metrics_summary)

        status.has_metrics = all(has_metrics)
        if status.has_metrics and len(metrics_summary):
            status.metrics_summary = sum(metrics_summary) / len(metrics_summary)

    style = __badge_style(request)
    return __produce_badge(title_text, status, style, hide_zeros=hide_zeros)

import svgwrite

from django.http import HttpResponse

from squad.core.models import ProjectStatus
from squad.frontend.views import get_build
from squad.http import auth


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

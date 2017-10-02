from django import template
from squad.core.utils import format_metadata


register = template.Library()


@register.simple_tag
def tabulate_test_comparison(comparison, test_results=None):
    if test_results is None:
        test_results = comparison.results
    if not test_results:
        return '(none)'

    text = []
    header = []
    indent = 0
    header_sep = ''
    row_format = ''
    for env in comparison.all_environments:
        for build in comparison.builds:
            header.append((build, env))
            text.append("%s+--- %s, %s" % ('|    ' * indent, build.version, env))
            indent += 1
            row_format += '%-4s '
            header_sep += '|    '
    row_format += '%s'  # for the test name

    text.append(header_sep)

    for test, results in test_results.items():
        row = []
        for build, env in header:
            row.append(results.get((build, env), 'n/a'))
        row.append(test)
        text.append(row_format % tuple(row))

    return "\n".join(text)


@register.filter
def metadata_txt(v, key=None):
    separator = " "
    if key:
        separator = "\n" + " " * (len(key) + 2)
    return format_metadata(v, separator)

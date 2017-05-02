from django import template
from tabulate import tabulate


register = template.Library()


@register.simple_tag
def tabulate_test_comparison(comparison, test_results=None):
    if test_results is None:
        test_results = comparison.results

    header = ["Test"]
    for build in comparison.builds:
        for env in comparison.environments[build]:
            header.append("%s (%s)" % (build.version, env))

    data = []
    for test, results in test_results.items():
        row = [test]
        for build in comparison.builds:
            for env in comparison.environments[build]:
                row.append(results.get((build, env)))
        data.append(row)

    return tabulate(data, header, 'grid')

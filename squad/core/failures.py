from django.core.paginator import Paginator
from squad.core.models import Test


class FailuresWithConfidence(object):
    def __init__(self, project, build, per_page=25, page=1, search=''):
        self.project = project
        self.build = build
        self.per_page = per_page
        self.page = page
        self.search = search

    __paginator__ = None

    @property
    def paginator(self):
        if self.__paginator__ is not None:
            return self.__paginator__

        names = self.build.tests.filter(
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

        if self.search:
            names = names.filter(metadata__name__icontains=self.search)

        self.__paginator__ = Paginator(names, self.per_page)
        return self.__paginator__

    @property
    def number(self):
        return self.page

    def failures(self):
        page = self.paginator.page(self.page)

        failures = self.build.tests.filter(
            result=False,
            metadata_id__in=[o.metadata__id for o in page.object_list],
        ).prefetch_related(
            'metadata', 'environment',
        ).order_by(
            'suite__slug', 'metadata__name'
        )

        limit = self.project.build_confidence_count
        builds = self.project.builds.filter(
            id__lt=self.build.id,
        ).order_by("-id").only("id")[:limit]

        previous = Test.objects.filter(
            metadata__in=[f.metadata for f in failures],
            environment__in=[f.environment for f in failures],
            build_id__in=list(builds.values_list("id", flat=True)),
        ).order_by("-build_id").prefetch_related("metadata", "environment").defer("log")

        for f in failures:
            f_p = [t for t in previous if t.metadata == f.metadata and t.environment == f.environment]
            f.set_confidence(self.project.build_confidence_threshold, f_p)

        return failures

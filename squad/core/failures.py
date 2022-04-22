from squad.core.models import Test


def failures_with_confidence(project, build, failures):
    fwc = build.tests.filter(
        result=False,
        metadata_id__in=[f.metadata__id for f in failures],
    ).prefetch_related(
        'metadata', 'environment',
    ).order_by(
        'suite__slug', 'metadata__name'
    )

    limit = project.build_confidence_count
    builds = project.builds.filter(
        id__lt=build.id,
    ).order_by("-id").only("id")[:limit]

    previous = Test.objects.filter(
        metadata__in=[f.metadata for f in fwc],
        environment__in=[f.environment for f in fwc],
        build_id__in=list(builds.values_list("id", flat=True)),
    ).order_by("-build_id").prefetch_related("metadata", "environment").defer("log")

    for f in fwc:
        f_p = [t for t in previous if t.metadata == f.metadata and t.environment == f.environment]
        f.set_confidence(project.build_confidence_threshold, f_p)

    return fwc

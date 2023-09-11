from django.db.models import prefetch_related_objects

from squad.core.models import Test


def failures_with_confidence(project, build, failures, releases_only=False):
    limit = project.build_confidence_count
    threshold = project.build_confidence_threshold

    prefetch_related_objects(failures, "metadata")

    queryset = project.builds.filter(id__lt=build.id)
    if releases_only:
        queryset = queryset.filter(is_release=True)
    builds = queryset.order_by('-id').all()[:limit]
    builds_ids = [b.id for b in builds]

    # Find previous `limit` tests that contain this test x environment
    for failure in failures:
        history = Test.objects.filter(
            build_id__in=builds_ids,
            metadata_id=failure.metadata_id,
            environment_id=failure.environment_id,
        ).only("result").order_by()

        failure.set_confidence(threshold, history)

    return failures

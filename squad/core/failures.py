from django.db.models import prefetch_related_objects

from squad.core.models import Test


def failures_with_confidence(project, build, failures):
    limit = project.build_confidence_count
    threshold = project.build_confidence_threshold

    prefetch_related_objects(failures, "metadata")

    # Find previous `limit` tests that contain this test x environment
    for failure in failures:
        history = Test.objects.filter(
            build_id__lt=build.id,
            metadata_id=failure.metadata_id,
            environment_id=failure.environment_id,
        ).order_by('-build_id').defer("log")[:limit]

        failure.set_confidence(threshold, history)

    return failures

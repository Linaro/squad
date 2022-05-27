from squad.core.models import Test


def failures_with_confidence(project, build, failures):
    limit = project.build_confidence_count
    threshold = project.build_confidence_threshold

    # First, get a list of failures x environments
    with_envs = build.tests.filter(
        metadata_id__in=[f.metadata__id for f in failures],
        result=False,
    ).exclude(
        has_known_issues=True
    ).prefetch_related(
        "metadata",
        "environment",
    ).order_by(
        "metadata__suite",
        "metadata__name",
    )

    # Find previous `limit` tests that contain this test x environment
    for failure in with_envs:
        history = Test.objects.filter(
            build_id__lt=build.id,
            metadata_id=failure.metadata_id,
            environment_id=failure.environment_id,
        ).order_by('-build_id').defer("log")[:limit]

        failure.set_confidence(threshold, history)

    return with_envs

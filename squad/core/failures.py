from squad.core.models import Test, SuiteMetadata


def failures_with_confidence(project, build, failures):
    limit = project.build_confidence_count
    threshold = project.build_confidence_threshold

    # Find previous `limit` tests that contain this test x environment
    tests_with_confidence = []
    for failure in failures:
        metadata = SuiteMetadata(
            suite=failure.metadata__suite,
            name=failure.metadata__name,
        )
        test = Test()
        test.metadata_id = failure.metadata_id
        test.environment_id = failure.environment_id
        test.build_id = build.id
        test.metadata = metadata

        history = Test.objects.filter(
            build_id__lt=build.id,
            metadata_id=failure.metadata_id,
            environment_id=failure.environment_id,
        ).order_by('-build_id').defer("log")[:limit]

        test.set_confidence(threshold, history)
        tests_with_confidence.append(test)

    return tests_with_confidence

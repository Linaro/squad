import logging

from django.db.models import Q
from django.core.management.base import BaseCommand

from squad.core.models import Test, SuiteMetadata
from squad.core.utils import split_list


logger = logging.getLogger()


class Command(BaseCommand):

    help = """fix suite in SuiteMetadata for cts/vts tests"""

    def handle(self, *args, **options):
        android_suites = ['cts', 'vts']
        condition = Q(suite__icontains=android_suites[0])
        condition |= Q(suite__icontains=android_suites[1])
        cts_and_vts_metadata = SuiteMetadata.objects.filter(condition, kind='test').order_by('-id')
        buggy_metadata = []
        for s in cts_and_vts_metadata:
            print("Processing SuiteMetedata with suite %s and test %s" % (s.suite, s.name), flush=True)
            first_test = Test.objects.filter(metadata=s).first()
            if first_test is None:
                buggy_metadata.append(s.id)
                print("# of orphan bad metadata found: %s" % len(buggy_metadata), flush=True)
                continue
            print("Found Test for above Suitemetadata. Test.suite is %s " % first_test.suite, flush=True)
            correct_suite = first_test.suite.slug
            if correct_suite != s.suite:
                correct_metadata = SuiteMetadata.objects.filter(kind='test', suite=correct_suite, name=s.name).first()
                if correct_metadata:
                    print("Found existing SuiteMetadata with correct suite: %s. Will use it to update all affected tests" % correct_metadata, flush=True)
                    print("correct_metadata: %s" % correct_metadata.id, flush=True)
                    print("Updating tests", flush=True)
                    all_affected_tests = Test.objects.filter(metadata=s)
                    print("# of affected tests: %s" % all_affected_tests.update(metadata=correct_metadata))
                else:
                    print('No existing correct metadata. Updating the corrupt SuiteMetadata and saving it in place ', flush=True)
                    s.suite = first_test.suite.slug
                    s.save()
            print('Done', flush=True)

        print("Completed Fixing all SuiteMetadata")
        print("Total number of orphan bad metadata found is: %s" % len(buggy_metadata))
        print("Starting to delete it in chunks")
        for chunk in split_list(buggy_metadata, 1000):
            SuiteMetadata.objects.filter(id__in=chunk).delete()
            print("Deleted 1000 bad metadata. Remaining: %s" % len(buggy_metadata))
        print("Cleaning All bad metadata concluded")

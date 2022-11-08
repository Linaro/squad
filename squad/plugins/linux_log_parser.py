import hashlib
import logging
import re
from collections import defaultdict
from squad.plugins import Plugin as BasePlugin
from squad.core.models import SuiteMetadata


logger = logging.getLogger()

REGEX_NAME = 0
REGEX_BODY = 1

MULTILINERS = [
    ('check-kernel-exception', r'-+\[ cut here \]-+.*?-+\[ end trace \w* \]-+'),
    ('check-kernel-kasan', r'=+\n\[[\s\.\d]+\]\s+BUG: KASAN:.*?=+'),
    ('check-kernel-kfence', r'=+\n\[[\s\.\d]+\]\s+BUG: KFENCE:.*?=+'),
]

ONELINERS = [
    ('check-kernel-oops', r'^[^\n]+Oops(?: -|:).*?$'),
    ('check-kernel-fault', r'^[^\n]+Unhandled fault.*?$'),
    ('check-kernel-warning', r'^[^\n]+WARNING:.*?$'),
    ('check-kernel-bug', r'^[^\n]+(?: kernel BUG at|BUG:).*?$'),
    ('check-kernel-invalid-opcode', r'^[^\n]+invalid opcode:.*?$'),
    ('check-kernel-panic', r'Kernel panic - not syncing.*?$'),
]

# Tip: broader regexes should come first
REGEXES = MULTILINERS + ONELINERS


class Plugin(BasePlugin):
    def __compile_regexes(self, regexes):
        combined = [r'(%s)' % r[REGEX_BODY] for r in regexes]
        return re.compile(r'|'.join(combined), re.S | re.M)

    def __cutoff_boot_log(self, log):
        # Attempt to split the log in " login:"
        logs = log.split(' login:', 1)

        # 1 string means no split was done, consider all logs as test log
        if len(logs) == 1:
            return '', log

        boot_log = logs[0]
        test_log = logs[1]
        return boot_log, test_log

    def __kernel_msgs_only(self, log):
        kernel_msgs = re.findall(r'(\[[ \d]+\.[ \d]+\] .*?)$', log, re.S | re.M)
        return '\n'.join(kernel_msgs)

    def __join_matches(self, matches, regexes):
        """
            group regex in python are returned as a list of tuples which each
            group match in one of the positions in the tuple. Example:
            regex = r'(a)|(b)|(c)'
            matches = [
                ('match a', '', ''),
                ('', 'match b', ''),
                ('match a', '', ''),
                ('', '', 'match c')
            ]
        """
        snippets = {regex_id: [] for regex_id in range(len(regexes))}
        for match in matches:
            for regex_id in range(len(regexes)):
                if len(match[regex_id]) > 0:
                    snippets[regex_id].append(match[regex_id])
        return snippets

    def __create_tests(self, testrun, suite, test_name, lines):
        """
        There will be at least one test per regex. If there were any match for a given
        regex, then a new test will be generated using test_name + shasum. This helps
        comparing kernel logs accross different builds
        """
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name=test_name, kind='test')
        testrun.tests.create(
            suite=suite,
            result=(len(lines) == 0),
            log='\n'.join(lines),
            metadata=metadata,
            build=testrun.build,
            environment=testrun.environment,
        )

        # Some lines of the matched regex might be the same, and we don't want to create
        # multiple tests like test1-sha1, test1-sha1, etc, so we'll create a set of sha1sums
        # then create only new tests for unique sha's
        shas = defaultdict(set)
        for line in lines:
            sha = self.__create_shasum(line)
            shas[sha].add(line)

        for sha, lines in shas.items():
            name = f'{test_name}-{sha}'
            metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name=name, kind='test')
            testrun.tests.create(
                suite=suite,
                result=False,
                log='\n---\n'.join(lines),
                metadata=metadata,
                build=testrun.build,
                environment=testrun.environment,
            )

    def __create_shasum(self, snippet):
        sha = hashlib.sha256()
        without_numbers = re.sub(r'(0x[a-f0-9]+|[<\[][0-9a-f]+?[>\]]|\d+)', '', snippet)
        without_time = re.sub(r'^\[[^\]]+\]', '', without_numbers)
        sha.update(without_time.encode())
        return sha.hexdigest()

    def postprocess_testrun(self, testrun):
        if testrun.log_file is None:
            return

        boot_log, test_log = self.__cutoff_boot_log(testrun.log_file)
        logs = {
            'boot': boot_log,
            'test': test_log,
        }

        for log_type, log in logs.items():
            log = self.__kernel_msgs_only(log)
            suite, _ = testrun.build.project.suites.get_or_create(slug=f'log-parser-{log_type}')

            regex = self.__compile_regexes(REGEXES)
            matches = regex.findall(log)
            snippets = self.__join_matches(matches, REGEXES)

            # search onliners within multiliners
            multiline_matches = []
            for regex_id in range(len(MULTILINERS)):
                multiline_matches += snippets[regex_id]

            regex = self.__compile_regexes(ONELINERS)
            matches = regex.findall('\n'.join(multiline_matches))
            onliner_snippets = self.__join_matches(matches, ONELINERS)

            regex_id_offset = len(MULTILINERS)
            for regex_id in range(len(ONELINERS)):
                snippets[regex_id + regex_id_offset] += onliner_snippets[regex_id]

            for regex_id in range(len(REGEXES)):
                test_name = REGEXES[regex_id][REGEX_NAME]
                self.__create_tests(testrun, suite, test_name, snippets[regex_id])

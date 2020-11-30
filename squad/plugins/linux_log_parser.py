import logging
import re
from squad.plugins import Plugin as BasePlugin
from squad.core.models import SuiteMetadata


logger = logging.getLogger()

REGEX_NAME = 0
REGEX_BODY = 1

MULTILINERS = [
    ('check-kernel-exception', r'------------\[ cut here \]------------.*?------------\[ cut here \]------------'),
    ('check-kernel-trace', r'Stack:.*?---\[ end trace \w* \]---'),
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

    def __create_test(self, testrun, suite, test_name, lines):
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name=test_name, kind='test')
        testrun.tests.create(
            suite=suite,
            result=(len(lines) == 0),
            log='\n'.join(lines),
            metadata=metadata,
            build=testrun.build,
            environment=testrun.environment,
        )

    def postprocess_testrun(self, testrun):
        if testrun.log_file is None:
            return

        log = self.__kernel_msgs_only(testrun.log_file)
        suite, _ = testrun.build.project.suites.get_or_create(slug='linux-log-parser')
        test_name_suffix = '-%s' % testrun.job_id

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
            test_name = REGEXES[regex_id][REGEX_NAME] + test_name_suffix
            self.__create_test(testrun, suite, test_name, snippets[regex_id])

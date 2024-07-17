import hashlib
import logging
import re
from collections import defaultdict
from squad.plugins import Plugin as BasePlugin
from squad.core.models import SuiteMetadata
from django.template.defaultfilters import slugify


logger = logging.getLogger()

REGEX_NAME = 0
REGEX_BODY = 1
REGEX_EXTRACT_NAME = 2

MULTILINERS = [
    ('check-kernel-exception', r'-+\[? cut here \]?-+.*?-+\[? end trace \w* \]?-+', r"\d][^\+\n]*"),
    ('check-kernel-kasan', r'=+\n\[[\s\.\d]+\]\s+BUG: KASAN:.*?=+', r"BUG: KASAN:[^\+\n]*"),
    ('check-kernel-kfence', r'=+\n\[[\s\.\d]+\]\s+BUG: KFENCE:.*?=+', r"BUG: KFENCE:[^\+\n]*"),
]

ONELINERS = [
    ('check-kernel-oops', r'^[^\n]+Oops(?: -|:).*?$', r"Oops[^\+\n]*"),
    ('check-kernel-fault', r'^[^\n]+Unhandled fault.*?$', r"Unhandled [^\+\n]*"),
    ('check-kernel-warning', r'^[^\n]+WARNING:.*?$', r"WARNING: [^\+\n]*"),
    ('check-kernel-bug', r'^[^\n]+(?: kernel BUG at|BUG:).*?$', r"BUG: [^\+\n]*"),
    ('check-kernel-invalid-opcode', r'^[^\n]+invalid opcode:.*?$', r"invalid opcode: [^\+\n]*"),
    ('check-kernel-panic', r'Kernel panic - not syncing.*?$', r"Kernel [^\+\n]*"),
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

    def __create_tests(self, testrun, suite, test_name, lines, test_regex=None):
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
            name = self.__create_name(line, test_regex)
            if name:
                sha = f"{name}-{sha}"
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

    def __remove_numbers_and_time(self, snippet):
        without_numbers = re.sub(r"(0x[a-f0-9]+|[<\[][0-9a-f]+?[>\]]|\d+)", "", snippet)
        without_time = re.sub(r"^\[[^\]]+\]", "", without_numbers)

        return without_time

    def __create_name(self, snippet, regex=None):
        matches = None
        if regex:
            matches = regex.findall(snippet)
        if not matches:
            return None
        snippet = matches[0]
        without_numbers_and_time = self.__remove_numbers_and_time(snippet)

        # Limit the name length to 191 characters, since the max name length
        # for SuiteMetadata in SQUAD is 256 characters. The SHA and "-" take 65
        # characters: 256-65=191
        return slugify(without_numbers_and_time)[:191]

    def __create_shasum(self, snippet):
        sha = hashlib.sha256()
        without_numbers_and_time = self.__remove_numbers_and_time(snippet)
        sha.update(without_numbers_and_time.encode())
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

            for regex_id in range(len(REGEXES)):
                test_name = REGEXES[regex_id][REGEX_NAME]
                regex_pattern = REGEXES[regex_id][REGEX_EXTRACT_NAME]
                test_name_regex = None
                if regex_pattern:
                    test_name_regex = re.compile(regex_pattern, re.S | re.M)
                self.__create_tests(testrun, suite, test_name, snippets[regex_id], test_name_regex)

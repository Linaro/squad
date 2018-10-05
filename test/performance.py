from contextlib import contextmanager
import json
import os
import re
import sys
from django.conf import settings
from django.db import connection, reset_queries


count = {}


@contextmanager
def count_queries(k):
    q = 0
    debug = settings.DEBUG
    try:
        settings.DEBUG = True
        reset_queries()
        yield
        q = len(connection.queries)
    finally:
        settings.DEBUG = debug
    count.setdefault(k, 0)
    count[k] += q
    return q


def export(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)
    if os.path.exists(f):
        diff(f)
    with open(f, 'w') as output:
        output.write(json.dumps(count))


def diff(previous_file):
    previous = json.loads(open(previous_file).read())
    improvements = []
    regressions = []
    for k, v in count.items():
        if k in previous:
            v0 = previous[k]
            if v > v0:
                regressions.append((k, v0, v))
            elif v < v0:
                improvements.append((k, v0, v))
    if improvements:
        list_changes(improvements, 'DATABASE PERFORMANCE IMPROVEMENTS')
    if regressions:
        list_changes(regressions, 'DATABASE PERFORMANCE REGRESSIONS')
        print('')
        print('If there are good reasons for the increase(s) above (e.g. new features), just remove `%s` and carry on. You will not be bothered again.' % previous_file)
        sys.exit(1)


def list_changes(data, title):
    print('')
    print(title)
    print(re.sub('.', '-', title))
    print('Unit: number of database queries')
    print('')
    for k, v0, v in data:
        print("%s: %d -> %d" % (k, v0, v))

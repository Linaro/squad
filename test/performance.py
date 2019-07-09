from contextlib import contextmanager
import json
import os
import re
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
        log_queries(k, connection.queries)
    finally:
        settings.DEBUG = debug
    count.setdefault(k, 0)
    count[k] += q
    return q


def log_queries(k, queries):
    os.makedirs('tmp/queries', exist_ok=True)
    with open('tmp/queries/%s.log' % re.sub('/', '_', k), 'w') as log:
        for query in connection.queries:
            log.write(repr(query))
            log.write("\n")


def export(f='tmp/queries.json'):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)
    rc = 0
    if os.path.exists(f):
        rc = diff(f)
    if rc == 0:
        with open(f, 'w') as output:
            output.write(json.dumps(count, indent=4))
    return rc


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
        print('If there are good reasons for the increase(s) above (e.g. new features, or new tests), just remove `%s` and carry on. You will not be bothered again.' % previous_file)
        print('Otherwise, you might want to investigate the reason for the extra database queries.')
        return 1
    return 0


def list_changes(data, title):
    print('')
    print(title)
    print(re.sub('.', '-', title))
    print('Unit: number of database queries')
    print('')
    for k, v0, v in data:
        print("%s: %d -> %d" % (k, v0, v))

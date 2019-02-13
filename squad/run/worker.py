import os
import sys


def main():
    argv = [
        sys.executable, '-m', 'celery',
        # default celery args:
        '-A', 'squad',
        'worker',
        '--concurrency=1',
        '--queues=celery,reporting_queue',
        '--max-tasks-per-child=5000',
        '--max-memory-per-child=1500000',
        '--loglevel=INFO'
    ] + sys.argv[1:]
    os.execvp(sys.executable, argv)


if __name__ == "__main__":
    main()

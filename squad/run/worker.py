from squad.settings import CELERY_TASK_ROUTES, CELERY_TASK_DEFAULT_QUEUE
import os
import sys


def main():
    queues = set([conf['queue'] for _, conf in CELERY_TASK_ROUTES.items()])
    queues.add(CELERY_TASK_DEFAULT_QUEUE)
    argv = [
        sys.executable, '-m', 'celery',
        # default celery args:
        '-A', 'squad',
        'worker',
        '--queues=' + ','.join(queues),
        '--max-tasks-per-child=5000',
        '--max-memory-per-child=1500000',
        '--loglevel=INFO'
    ] + sys.argv[1:]
    os.execvp(sys.executable, argv)


if __name__ == "__main__":
    main()

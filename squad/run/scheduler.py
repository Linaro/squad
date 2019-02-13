import os
import sys


def main():
    argv = [
        sys.executable, '-m', 'celery',
        # default celery args:
        '-A', 'squad',
        'beat',
        '--pidfile=',
    ] + sys.argv[1:]
    os.execvp(sys.executable, argv)


if __name__ == "__main__":
    main()

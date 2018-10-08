import os
import sys


def main():
    testing = False
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test.settings")
        testing = True
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squad.settings")
    from django.core.management import execute_from_command_line
    try:
        execute_from_command_line(sys.argv)
    finally:
        if testing:
            import test.performance
            test.performance.export('tmp/queries.json')


if __name__ == "__main__":
    main()

import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test.settings")
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squad.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

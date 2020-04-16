import os
import sys


def main():
    testing = False
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test.settings")
        testing = True

        exclude_tags = os.getenv('SQUAD_EXCLUDE_TEST_TAGS')
        if exclude_tags:
            tags = exclude_tags.split()
            for tag in tags:
                sys.argv += ['--exclude-tag', tag]
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "squad.settings")
    from django.core.management import execute_from_command_line
    try:
        execute_from_command_line(sys.argv)
    finally:
        if testing:
            sys.stdout.flush()
            sys.stderr.flush()
            tests = [t for t in sys.argv[2:] if t.startswith('test.')]
            __help = '--help' in sys.argv or '-h' in sys.argv
            if not tests and not __help:
                # only run when not running specific tests
                rc = performance_tests()
                rc += javascript_tests()
                if rc > 0:
                    sys.exit(rc)


def performance_tests():
    import test.performance
    return test.performance.export()


def javascript_tests():
    import test.javascript
    return test.javascript.javascript_tests()


if __name__ == "__main__":
    main()

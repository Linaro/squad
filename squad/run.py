import os
from pkg_resources import load_entry_point
import sys
from squad.version import __version__
from squad.manage import main as manage


__usage__ = """usage: squad [OPTIONS]

Options:

  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit

  ALL other options are passed as-is to gunicorn. See gunicorn(1), gunicorn3(1)
  `gunicorn --help`, or `gunicorn3 --help` for details.
"""


def usage():
    print(__usage__)


def main():
    argv = sys.argv

    if '--help' in argv or '-h' in argv:
        usage()
        return

    if '--version' in argv or '-v' in argv:
        print('squad (version %s)' % __version__)
        return

    os.environ.setdefault("ENV", "production")

    sys.argv = ['squad-admin', 'migrate']
    manage()

    sys.argv = ['squad-admin', 'collectstatic', '--no-input', '-v', '0']
    manage()

    os.system('sh -c "echo $PATH"')
    os.system('rm -f /tmp/foo')

    argv = ['python3', '-m', 'gunicorn.app.wsgiapp', 'squad.wsgi'] + argv[1:]
    os.execvp('python3', argv)


if __name__ == "__main__":
    main()

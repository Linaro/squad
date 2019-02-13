import os
import sys
from squad.version import __version__
from squad.manage import main as manage


__usage__ = """usage: squad [OPTIONS]

Options:

    -f, --fast          Fast startup: skip potentially slow operations, such as
                        running database migrations and compiling static assets
    -h, --help          show this help message and exit
    -v, --version       show program's version number and exit

    ALL other options are passed as-is to gunicorn. See gunicorn(1),
    gunicorn3(1), or http://docs.gunicorn.org/ for details.

gunicorn options:\
"""


def usage():
    print(__usage__)
    sys.stdout.flush()
    os.system(r'%s -m gunicorn.app.wsgiapp --help | sed -e "/^\S/d"' % sys.executable)


def main():
    argv = sys.argv
    fast = False

    for f in ['--fast', '-f']:
        if f in argv:
            argv.remove(f)
            fast = True

    if '--help' in argv or '-h' in argv:
        usage()
        return

    if '--version' in argv or '-v' in argv:
        print('squad (version %s)' % __version__)
        return

    os.environ.setdefault("ENV", "production")

    if not fast:
        sys.argv = ['squad-admin', 'migrate']
        manage()
        sys.argv = ['squad-admin', 'collectstatic', '--no-input', '-v', '0']
        manage()

    argv = [sys.executable, '-m', 'gunicorn.app.wsgiapp', 'squad.wsgi'] + argv[1:]
    os.execv(sys.executable, argv)

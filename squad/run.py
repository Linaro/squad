import os
from pkg_resources import load_entry_point
import sys
from squad.version import __version__
from squad.manage import main as manage


def main():
    gunicorn = load_entry_point('gunicorn', 'console_scripts', 'gunicorn')

    os.putenv("ENVIRONMENT", "production")
    os.putenv('DJANGO_SETTINGS_MODULE', 'squad.settings')

    print('---------------------------------------')
    print('Running SQUAD version %s' % __version__)
    print('Type control-C to stop')
    print('---------------------------------------')
    print('')

    sys.argv = ['squad-admin', 'migrate']
    manage()

    sys.argv = ['gunicorn', 'squad.wsgi'] + sys.argv[1:]
    gunicorn()


if __name__ == "__main__":
    main()

import os
import subprocess

static = os.path.join(os.path.dirname(__file__), 'static')


def setup_staticfiles():
    subprocess.check_call(['./download'], cwd=static)

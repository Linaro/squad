import os
import subprocess

static = os.path.join(os.path.dirname(__file__), 'static')

subprocess.check_call(['./download'], cwd=static)

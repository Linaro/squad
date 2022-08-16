import os
import re
import sys
from setuptools import setup, find_packages


__version__ = None
exec(open('squad/version.py').read())


def valid_requirement(req):
    return not (re.match(r'^\s*$', req) or re.match('^#', req))


requirements_txt = open('requirements.txt').read().splitlines()
requirements = [req for req in requirements_txt if valid_requirement(req)]
if os.getenv('REQ_IGNORE_VERSIONS'):
    requirements = [req.split('>=')[0] for req in requirements]

extras_require = {
    'postgres': 'psycopg2',
}


if len(sys.argv) > 1 and sys.argv[1] in ['sdist', 'bdist', 'bdist_wheel'] and not os.getenv('SQUAD_RELEASE'):
    raise RuntimeError('Please use scripts/release to make releases!')

setup(
    name='squad',
    version=__version__,
    author='Antonio Terceiro',
    author_email='antonio.terceiro@linaro.org',
    url='https://github.com/Linaro/squad',
    packages=find_packages(exclude=['test*']),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'squad-admin=squad.manage:main',
            'squad=squad.run:main',
            'squad-worker=squad.run.worker:main',
            'squad-listener=squad.run.listener:main',
            'squad-scheduler=squad.run.scheduler:main',
        ]
    },
    install_requires=requirements,
    extras_require=extras_require,
    license='GPLv3+',
    description="Software Quality Dashboard",
    long_description="Software Quality Dashboard",  # FIXME
    platforms='any',
)

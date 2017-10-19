import re
from setuptools import setup, find_packages


__version__ = None
exec(open('squad/version.py').read())


def valid_requirement(req):
    return not (re.match('^\s*$', req) or re.match('^#', req))


requirements_txt = open('requirements.txt').read().splitlines()
requirements = [req for req in requirements_txt if valid_requirement(req)]


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
        ]
    },
    install_requires=requirements,
    license='AGPLv3+',
    description="Software Quality Dashboard",
    long_description="Software Quality Dashboard",  # FIXME
    platforms='any',
)

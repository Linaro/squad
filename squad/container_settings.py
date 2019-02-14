# This file contains reasonable default settings to run SQUAD inside an
# application container, such as Docker. Runnind SQUAD in a system container
# (e.g. LXC) should not require special configuration.
#
# To use this, create a symbolic link called local_settings.py pointing to this
# file, e.g.:
#
#   $ cd squad && ln -s container_settings.py local_settings.py

import subprocess

from squad.settings import EMAIL_HOST


__implicit_email_host__ = """
########################################################################
# WARNING: IMPLICIT CONFIGURATION EMAIL HOST
#
# SQUAD is currently using the container host IP address, %s,
# as server for sending e-mail. For this to work, the container host
# must be running an MTA on port 25, and accepting connections from
# containers. If that is not the case, you need to explicitly configure
# which server to use for outgoing mail through the $SQUAD_EMAIL_HOST
# environment variable.
########################################################################
"""
if EMAIL_HOST == 'localhost':
    EMAIL_HOST = subprocess.check_output(
        ['ip', 'route', 'show', '0.0.0.0/0']
    ).split()[2].decode()
    print(__implicit_email_host__ % EMAIL_HOST)

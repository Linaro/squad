import sys

if sys.version_info.major >= 3 and sys.version_info.minor >= 3:
    from unittest.mock import *  # noqa
else:
    from mock import *  # noqa

import re
import os
from glob import glob
from importlib import import_module


__ALL_BACKENDS__ = []


for filename in sorted(glob(os.path.dirname(__file__) + '/*.py')):
    name = re.sub('.py$', '', os.path.basename(filename))
    if name != '__init__':
        __ALL_BACKENDS__.append(name)


ALL_BACKENDS = tuple(((name, name) for name in __ALL_BACKENDS__))


def get_backend_implementation(backend):
    name = backend.implementation_type
    module = import_module('squad.ci.backend.' + name)
    return module.Backend(backend)

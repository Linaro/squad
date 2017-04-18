import re
import os
from collections import OrderedDict
from glob import glob
from importlib import import_module


__ALL_BACKENDS__ = OrderedDict()


for filename in sorted(glob(os.path.dirname(__file__) + '/*.py')):
    name = re.sub('.py$', '', os.path.basename(filename))
    if name != '__init__':
        module = import_module('squad.ci.backend.' + name)
        __ALL_BACKENDS__[name] = (module.Backend, module.description)


ALL_BACKENDS = tuple(((key, details[1]) for key, details in __ALL_BACKENDS__.items()))


def get_backend_implementation(backend):
    return __ALL_BACKENDS__[backend.implementation_type][0](backend)

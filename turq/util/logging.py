# pylint: disable=invalid-name

import logging


def instanceLogger(obj):
    name = '%s.%s.%x' % (obj.__class__.__module__, obj.__class__.__name__,
                         id(obj))
    return logging.getLogger(name)

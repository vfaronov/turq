# pylint: disable=invalid-name

import collections
import logging
import threading

counts = collections.defaultdict(int)
lock = threading.Lock()


def getNextLogger(prefix):
    # This is an easy way to distinguish log messages from different objects,
    # and to selectively enable debug logging only for some of them.
    with lock:
        counts[prefix] += 1
        return logging.getLogger('%s.%d' % (prefix, counts[prefix]))

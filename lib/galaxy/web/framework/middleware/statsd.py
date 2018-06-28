"""
Middleware for sending request statistics to statsd
"""
from __future__ import absolute_import

import time

try:
    import statsd
except ImportError:
    # This middleware will never be used without statsd.  This block allows
    # unit tests pass on systems without it.
    statsd = None


class StatsdMiddleware(object):
    """
    This middleware will log request durations to the configured statsd
    instance.
    """

    def __init__(self,
                 application,
                 statsd_host,
                 statsd_port,
                 statsd_prefix):
        if not statsd:
            raise ImportError("Statsd middleware configured, but no statsd python module found. "
                           "Please install the python statsd module to use this functionality.")
        self.application = application
        self.statsd_client = statsd.StatsClient(statsd_host, statsd_port, prefix=statsd_prefix)

    def __call__(self, environ, start_response):
        start_time = time.time()
        req = self.application(environ, start_response)
        dt = int((time.time() - start_time) * 1000)
        self.statsd_client.timing(environ.get('controller_action_key', None) or environ.get('PATH_INFO', "NOPATH").strip('/').replace('/', '.'), dt)
        return req

from datetime import datetime
import http.server
import socket

import werkzeug.http


# https://www.iana.org/assignments/http-methods/http-methods.xhtml
KNOWN_METHODS = ['ACL', 'BASELINE-CONTROL', 'BIND', 'CHECKIN', 'CHECKOUT',
                 'CONNECT', 'COPY', 'DELETE', 'GET', 'HEAD', 'LABEL', 'LINK',
                 'LOCK', 'MERGE', 'MKACTIVITY', 'MKCALENDAR', 'MKCOL',
                 'MKREDIRECTREF', 'MKWORKSPACE', 'MOVE', 'OPTIONS',
                 'ORDERPATCH', 'PATCH', 'POST', 'PRI', 'PROPFIND', 'PROPPATCH',
                 'PUT', 'REBIND', 'REPORT', 'SEARCH', 'TRACE', 'UNBIND',
                 'UNCHECKOUT', 'UNLINK', 'UNLOCK', 'UPDATE',
                 'UPDATEREDIRECTREF', 'VERSION-CONTROL']


def default_reason(status_code):
    common_phrases = http.server.BaseHTTPRequestHandler.responses
    (reason, _) = common_phrases.get(status_code, ('Unknown', None))
    return reason


def error_explanation(status_code):
    common_phrases = http.server.BaseHTTPRequestHandler.responses
    (_, explanation) = common_phrases.get(status_code,
                                          (None, 'Something is wrong'))
    return explanation


def date():
    return werkzeug.http.http_date(datetime.utcnow())


def nice_header_name(name):
    # "cache-control" -> "Cache-Control"
    return '-'.join(word.capitalize() for word in name.split('-'))


def guess_external_url(local_host, port):
    """Return a URL that is most likely to route to `local_host` from outside.

    The point is that we may be running on a remote host from the user's
    point of view, so they can't access `local_host` from a Web browser just
    by typing ``http://localhost:12345/``.
    """
    if local_host in ['0.0.0.0', '::']:         # Listening on all interfaces
        local_host = socket.getfqdn()
        # https://github.com/vfaronov/turq/issues/9
        if local_host.lower().rstrip('.').endswith('.arpa'):
            local_host = 'localhost'          # Welp, not much we can do here.
    if ':' in local_host:     # IPv6 literal
        local_host = '[%s]' % local_host
    return 'http://%s:%d/' % (local_host, port)

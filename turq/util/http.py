from datetime import datetime
import http.server
from ipaddress import IPv6Address
import re
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


IPV4_REVERSE_DNS = re.compile(r'^' + r'([0-9]+)\.' * 4 + r'in-addr\.arpa\.?$',
                              flags=re.IGNORECASE)
IPV6_REVERSE_DNS = re.compile(r'^' + r'([0-9a-f])\.' * 32 + r'ip6\.arpa\.?$',
                              flags=re.IGNORECASE)


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
    if local_host in ['0.0.0.0', '::']:
        # The server is listening on all interfaces, but we have to pick one.
        # The system's FQDN should give us a hint.
        local_host = socket.getfqdn()

        # https://github.com/vfaronov/turq/issues/9
        match = IPV4_REVERSE_DNS.match(local_host)
        if match:
            local_host = '.'.join(reversed(match.groups()))
        else:
            match = IPV6_REVERSE_DNS.match(local_host)
            if match:
                address_as_int = int(''.join(reversed(match.groups())), 16)
                local_host = str(IPv6Address(address_as_int))

    if ':' in local_host:
        # Looks like an IPv6 literal. Has to be wrapped in brackets in a URL.
        # Also, an IPv6 address can have a zone ID tacked on the end,
        # like "%3". RFC 6874 allows encoding them in URLs as well,
        # but in my experiments on Windows 8.1, I had more success
        # removing the zone ID altogether. After all this is just a guess.
        local_host = '[%s]' % local_host.rsplit('%', 1)[0]

    return 'http://%s:%d/' % (local_host, port)

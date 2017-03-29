from datetime import datetime
import http.server

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

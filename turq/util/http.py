from datetime import datetime
import http.server

import werkzeug.http


def default_reason(status_code):
    common_phrases = http.server.BaseHTTPRequestHandler.responses
    (reason, _) = common_phrases.get(status_code, ('Unknown', None))
    return reason


def date():
    return werkzeug.http.http_date(datetime.utcnow())

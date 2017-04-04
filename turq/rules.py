# pylint: disable=protected-access

import cgi
import contextlib
import gzip
import io
import json
import logging
import random
import re
import socket
import ssl
import time
import traceback
from urllib.parse import parse_qs, urlparse
import wsgiref.headers

import dominate
import dominate.tags as H
import h11

from turq.util.http import (KNOWN_METHODS, date, default_reason,
                            error_explanation, nice_header_name)
from turq.util.logging import getNextLogger
from turq.util.text import ellipsize, force_bytes, lorem_ipsum


RULES_FILENAME = '<rules>'


class RulesContext:

    # An instance of `RulesContext` is responsible for handling
    # one request according to the rules provided by the user.
    # It receives `h11` events from its `MockHandler`,
    # converts them into a convenient `Request` representation,
    # executes the rules code to fill out the `Response`,
    # converts the `Response` into `h11` events
    # and sends them back to the `MockHandler`.

    # pylint: disable=attribute-defined-outside-init

    def __init__(self, code, handler):
        self._code = code
        self._handler = handler
        self._logger = getNextLogger('turq.request')

    def _run(self, event):
        self.request = Request(
            self, event.method.decode(), event.target.decode(),
            event.http_version.decode(), _decode_headers(event.headers),
        )
        self._logger.info('> %s', ellipsize(self.request.line, 100))
        self._log_headers(self.request.raw_headers)
        self._response = Response()
        self._scope = self._build_scope()
        try:
            exec(self._code, self._scope)        # pylint: disable=exec-used
        except SkipRemainingRules:
            pass
        except Exception as exc:
            self._log_rules_error(exc)
            if self._handler.our_state is h11.SEND_RESPONSE:
                # We can still replace the response with a 500.
                self._response = Response()
                self.error(500)

        # Depending on the rules, at this point the request body may or may not
        # have been received, and the response may or may not have been sent.
        # We need to make sure everything is flushed.
        self._ensure_request_received()
        self.flush()

    def _log_headers(self, headers):
        for (name, value) in headers:
            self._logger.debug('+ %s: %s', name, value)

    def _build_scope(self):
        # Assemble the global scope in which the rules will be executed.
        # This includes all "public" attributes of `RulesContext`...
        scope = {name: getattr(self, name)
                 for name in dir(self) if not name.startswith('_')}
        # ...shortcuts for common request methods
        for method in KNOWN_METHODS:
            scope[method.replace('-', '_')] = (self.method == method)
        # ...Dominate's HTML tags library
        scope['H'] = H
        # ...utility functions
        for func in [lorem_ipsum, time.sleep]:
            scope[func.__name__] = func
        return scope

    def _log_rules_error(self, exc):
        # Extract the rules line number where the error happened.
        [lineno, *_] = [lineno
                        for (filename, lineno, _, _)
                        in reversed(traceback.extract_tb(exc.__traceback__))
                        if filename == RULES_FILENAME]
        self._logger.error('error in rules, line %d: %s', lineno, exc)
        self._logger.debug('details of this error:', exc_info=True)

    def _ensure_request_received(self):
        if self._handler.their_state is h11.SEND_BODY:
            self._receive_body()

    def flush(self, body_too=True):
        if self._handler.our_state is h11.SEND_RESPONSE:
            self._send_response()
            # Clear the list of response headers: from this point on,
            # any headers added will be sent in the trailer part.
            self._response.raw_headers[:] = []
        if body_too and self._handler.our_state is h11.SEND_BODY:
            self._send_body()

    def _receive_body(self):
        chunks = []
        while True:
            event = self._handler.receive_event()
            if isinstance(event, h11.Data):
                chunks.append(event.data)
            elif isinstance(event, h11.EndOfMessage):
                self.request._body = b''.join(chunks)
                self._logger.debug('received request body: %d bytes',
                                   len(self.request._body))
                # Add any trailer part to the main headers list
                trailer = _decode_headers(event.headers)
                self._log_headers(trailer)
                self.request.raw_headers += trailer
                break

    def _send_response(self, interim=False):
        self._response.finalize()
        self._logger.info('< %s', self._response.status_line)
        self._log_headers(self._response.raw_headers)
        cls = h11.InformationalResponse if interim else h11.Response
        self._handler.send_event(cls(
            http_version=self._response.http_version,
            status_code=self._response.status_code,
            reason=force_bytes(self._response.reason),
            headers=_encode_headers(self._response.raw_headers),
        ))

    def _send_body(self):
        if self._response.body:
            self.chunk(self._response.body)
        self._log_headers(self._response.raw_headers)
        self._handler.send_event(h11.EndOfMessage(
            headers=_encode_headers(self._response.raw_headers),
        ))

    def debug(self):
        if self._logger.getEffectiveLevel() > logging.DEBUG:
            self._logger.setLevel(logging.DEBUG)
            # Request headers were logged earlier in `_run`,
            # but the user didn't have a chance to see them
            # because debug logging was not yet enabled.
            self._log_headers(self.request.raw_headers)

    method = property(lambda self: self.request.method)
    target = property(lambda self: self.request.target)
    path = property(lambda self: self.request.path)
    query = property(lambda self: self.request.query)

    def status(self, code, reason=None):
        self._response.status_code = code
        self._response.reason = reason

    def header(self, name, value):
        self._response.headers[name] = value

    def add_header(self, name, value):
        self._response.headers.add_header(name, value)

    def delete_header(self, name):
        del self._response.headers[name]

    def body(self, data):
        if hasattr(data, 'read'):       # files
            data = data.read()
        self._response.body = force_bytes(data, 'utf-8')

    def chunk(self, data):
        self.flush(body_too=False)
        self._response.body = None          # So that `_send_body` skips it
        # Responses to HEAD can't have a message body. We magically skip
        # sending data in that case, so the user doesn't have to remember.
        # (204 and 304 responses also can't have a body, but those have to be
        # explicitly selected by the user, so it's their problem.)
        if self.method == 'HEAD':
            self._logger.debug('not sending %d bytes of response body '
                               'because request was HEAD', len(data))
        else:
            self._logger.debug('sending %d bytes of response body', len(data))
            self._handler.send_event(h11.Data(data=force_bytes(data)))

    def content_length(self):
        self._response.headers['Content-Length'] = \
            str(len(self._response.body))

    @contextlib.contextmanager
    def interim(self):
        main_response = self._response
        self._response = Response()
        self.status(100)
        yield
        self._send_response(interim=True)
        self._response = main_response

    def forward(self, hostname, port, target, tls=None):
        self._ensure_request_received()     # Get the trailer part, if any
        self._logger.debug('forwarding to %s port %d', hostname, port)
        self._response = forward(self.request, hostname, port, target, tls)
        self._logger.debug('upstream response: %s', self._response.status_line)

    def text(self, content):
        self.header('Content-Type', 'text/plain; charset=utf-8')
        self.body(content)

    def error(self, code):
        self.status(code)
        self.text('Error! %s\r\n' % error_explanation(code))

    def json(self, obj, jsonp=False):
        data = json.dumps(obj)
        if jsonp and self.request.query.get('callback'):
            self.header('Content-Type', 'application/javascript')
            # http://timelessrepo.com/json-isnt-a-javascript-subset
            data = (data.
                    replace('\u2028', '\\u2028').
                    replace('\u2029', '\\u2029'))
            self.body('%s(%s);' % (self.request.query['callback'], data))
        else:
            self.header('Content-Type', 'application/json')
            self.body(data)

    def route(self, spec):
        # Convert our simplistic route format to a regex to match the path.
        # First, we need to escape dots and such.
        spec = re.escape(spec)
        # This had the side effect of escaping colon as well,
        # so we need to compensate for it (note the backslashes):
        regex = '^%s$' % re.sub(r'\\:([A-Za-z_][A-Za-z0-9_]*)',
                                lambda m: '(?P<%s>[^/]+)' % m.group(1),
                                spec)
        match = re.match(regex, self.path)
        if match:
            self._scope.update(match.groupdict())
            return True
        else:
            return False

    def html(self):
        # If the user just calls ``html()``, we fill out a basic page.
        with self._edit_html():
            H.h1('Hello world!')
            H.p(lorem_ipsum())
            H.p(lorem_ipsum())
        # But then we also return the context manager that can be used
        # to rebuild the page as the user wishes. It does nothing unless
        # it is entered (``with``).
        return self._edit_html()

    @contextlib.contextmanager
    def _edit_html(self):
        document = dominate.document(title='Hello world')
        with document:
            yield document
        self.header('Content-Type', 'text/html; charset=utf-8')
        self.body(document.render())

    @staticmethod
    def maybe(p):
        return random.random() < p

    def send_raw(self, data):
        self._logger.info('sending %d bytes of raw data', len(data))
        self._handler.send_raw(force_bytes(data, 'utf-8'))

    def cors(self):
        headers = self.request.headers
        self.header('Access-Control-Allow-Origin', headers.get('Origin', '*'))
        self.header('Access-Control-Allow-Credentials', 'true')
        if self.method == 'OPTIONS' and 'Origin' in headers:
            self._logger.debug('responding to CORS preflight request')
            self.status(200)
            self.header('Access-Control-Allow-Methods',
                        headers.get('Access-Control-Request-Method', ''))
            self.header('Access-Control-Allow-Headers',
                        headers.get('Access-Control-Request-Headers', ''))
            self.body('')
            raise SkipRemainingRules()
        else:
            self.add_header('Vary', 'Origin')

    def basic_auth(self):
        self._require_auth('Basic', 'realm="Turq"')

    def digest_auth(self):
        self._require_auth('Digest', 'realm="Turq", qop="auth", nonce="12345"')

    def bearer_auth(self):
        self._require_auth('Bearer', 'scope="turq"')

    def _require_auth(self, scheme, challenge_params):
        authorization = self.request.headers.get('Authorization', '')
        if not authorization.lower().startswith(scheme.lower() + ' '):
            self._logger.debug('missing required Authorization: %s', scheme)
            self.error(401)
            self.header('WWW-Authenticate',
                        '%s %s' % (scheme, challenge_params))
            raise SkipRemainingRules()

    def gzip(self):
        buf = io.BytesIO()
        with gzip.GzipFile(mode='wb', compresslevel=4, fileobj=buf) as f:
            f.write(self._response.body)
        self.body(buf.getvalue())
        self.add_header('Content-Encoding', 'gzip')

    def redirect(self, location, status=302):
        self.status(status)
        self.header('Location', location)
        self.text('Please see %s\r\n' % location)


class SkipRemainingRules(Exception):

    pass


class Request:

    def __init__(self, context, method, target, http_version, headers):
        self._context = context
        self.method = method
        self.target = target
        parsed_url = urlparse(target)
        self.path = parsed_url.path
        self.query = _single_values(parse_qs(parsed_url.query))
        self.version = self.http_version = http_version
        self.raw_headers = headers
        self.headers = wsgiref.headers.Headers(self.raw_headers)
        self._body = None
        self._json = None
        self._form = None

        # Reconstructed request-line, for logging.
        self.line = '%s %s HTTP/%s' % (self.method, self.target,
                                       self.http_version)

    @property
    def body(self):
        # Request body is received lazily. This allows handling
        # finer aspects of the protocol, such as ``Expect: 100-continue``.
        if self._body is None:
            self._context._receive_body()
        return self._body

    # `json` and `form` are very heavy-handed with regard to encoding.
    # We don't care about applications that send JSON in UTF-16 or
    # Windows-1251 in URL encoding. Turq should be easy in the common case.

    @property
    def json(self):
        if self._json is None:
            try:
                self._json = json.loads(self.body.decode('utf-8'))
            except ValueError as exc:
                self._context._logger.debug('cannot read JSON: %s', exc)
        return self._json

    @property
    def form(self):
        if self._form is None:
            try:
                content_type = self.headers.get('Content-Type', '')
                type_, params = cgi.parse_header(content_type)
                if type_.lower() == 'multipart/form-data':
                    self._form = _parse_multipart(self.body, params)
                else:       # Assume URL-encoded
                    self._form = _single_values(parse_qs(self.body.decode()))
            except ValueError as exc:
                self._context._logger.debug('cannot read form: %s', exc)
        return self._form


class Response:

    def __init__(self):
        self.http_version = '1.1'
        self.status_code = 200
        self.reason = None
        self.raw_headers = []
        self.headers = wsgiref.headers.Headers(self.raw_headers)
        self.body = b''

    def finalize(self):
        # h11 only sends HTTP/1.1.
        self.http_version = '1.1'

        # h11 sends an empty reason phrase by default. While this is
        # correct with regard to the protocol, I think it will be
        # more convenient and less surprising to the user if we fill it.
        if self.reason is None:
            self.reason = default_reason(self.status_code)

        # RFC 7231 Section 7.1.1.2 requires a ``Date`` header
        # on all 2xx, 3xx, and 4xx responses.
        if 200 <= self.status_code <= 499 and 'Date' not in self.headers:
            self.headers['Date'] = date()

    @property
    def status_line(self):
        # Reconstructed status-line, for logging.
        return 'HTTP/%s %d %s' % (self.http_version,
                                  self.status_code, self.reason)


def _decode_headers(headers):
    # Header values can contain arbitrary bytes. Decode them from ISO-8859-1,
    # which is the historical encoding of HTTP. Decoding bytes from ISO-8859-1
    # is a lossless operation, it cannot fail. Also, h11 gives us all header
    # names in lowercase, but we force them to Message-Case for a more readable
    # output in `_log_headers`.
    return [(nice_header_name(name.decode()), value.decode('iso-8859-1'))
            for (name, value) in headers]

def _encode_headers(headers):
    return [(force_bytes(name), force_bytes(value))
            for (name, value) in headers]


def _parse_multipart(body, params):
    # Some ritual dance is required to get the `cgi` module work in 2017.
    body = io.BytesIO(body)
    params = {name: force_bytes(value) for (name, value) in params.items()}
    parsed = _single_values(cgi.parse_multipart(body, params))
    return {name: value.decode('utf-8') for (name, value) in parsed.items()}


def _single_values(parsed_dict):
    # For ease of use, leave only the first value for each name.
    return {name: value for name, (value, *_) in parsed_dict.items()}


def forward(request, hostname, port, target, tls=None):
    hconn = h11.Connection(our_role=h11.CLIENT)
    if tls is None:
        tls = (port == 443)
    headers = _forward_headers(request.raw_headers, request.http_version,
                               also_exclude=['Host'])
    # RFC 7230 recommends that ``Host`` be the first header.
    headers.insert(0, ('Host', _generate_host_header(hostname, port, tls)))
    headers.append(('Connection', 'close'))

    sock = socket.create_connection((hostname, port))

    try:
        if tls:
            # We intentionally ignore server certificates. In this context,
            # they are more likely to be a nuisance than a boon.
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            sock = ssl_context.wrap_socket(sock, server_hostname=hostname)
        sock.sendall(hconn.send(h11.Request(method=request.method,
                                            target=target,
                                            headers=_encode_headers(headers))))
        sock.sendall(hconn.send(h11.Data(data=request.body)))
        sock.sendall(hconn.send(h11.EndOfMessage()))

        response = Response()
        while True:
            # pylint: disable=no-member
            event = hconn.next_event()
            if event is h11.NEED_DATA:
                hconn.receive_data(sock.recv(4096))
            elif isinstance(event, h11.Response):
                response.http_version = event.http_version.decode()
                response.status_code = event.status_code
                # Reason phrases can contain arbitrary bytes.
                # See above regarding ISO-8859-1.
                response.reason = event.reason.decode('iso-8859-1')
                response.raw_headers[:] = _forward_headers(
                    _decode_headers(event.headers), response.http_version)
            elif isinstance(event, h11.Data):
                response.body += event.data
            elif isinstance(event, h11.EndOfMessage):
                return response

    except h11.RemoteProtocolError as exc:
        # https://github.com/njsmith/h11/issues/41
        raise RuntimeError(str(exc)) from exc

    finally:
        sock.close()


def _forward_headers(headers, http_version, also_exclude=None):
    # RFC 7230 Section 5.7
    connection_options = [option.strip().lower()
                          for (name, value) in headers
                          if name.lower() == 'connection'
                          for option in value.split(',')]
    also_exclude = [name.lower() for name in also_exclude or []]
    exclude = connection_options + ['connection'] + also_exclude
    filtered = [(name, value)
                for (name, value) in headers
                if name.lower() not in exclude]
    return filtered + [('Via', '%s turq' % http_version)]


def _generate_host_header(hostname, port, tls):
    if ':' in hostname:                     # IPv6 literal
        hostname = '[%s]' % hostname
    if port == (443 if tls else 80):        # Default port
        return hostname
    else:
        return '%s:%d' % (hostname, port)

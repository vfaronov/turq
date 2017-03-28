# pylint: disable=protected-access

import contextlib
import socket
import ssl
import time
import wsgiref.headers

import h11

import turq.util.http
import turq.util.logging
from turq.util.text import force_bytes, lorem_ipsum


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
        self._logger = turq.util.logging.instanceLogger(self)

    def _run(self):
        event = self._handler.receive_event()
        if isinstance(event, h11.ConnectionClosed):
            return
        assert isinstance(event, h11.Request)
        self.request = Request(
            self, event.method.decode(), event.target.decode(),
            event.http_version.decode(), _decode_headers(event.headers),
        )
        self._response = Response()
        self._scope = self._build_scope()
        exec(self._code, self._scope)        # pylint: disable=exec-used

        # Depending on the rules, at this point the request body may or may not
        # have been received, and the response may or may not have been sent.
        # We need to make sure everything is flushed.
        self._ensure_request_received()
        self.flush()

    def _build_scope(self):
        # Assemble the global scope in which the rules will be executed.
        # This includes all "public" attributes of `RulesContext`...
        scope = {name: getattr(self, name)
                 for name in dir(self) if not name.startswith('_')}
        # ...shortcuts for common request methods
        for method in turq.util.http.KNOWN_METHODS:
            scope[method.replace('-', '_')] = (self.method == method)
        # ...utility functions
        for func in [lorem_ipsum, time.sleep]:
            scope[func.__name__] = func
        return scope

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
                # Add any trailer part to the main headers list
                self.request.raw_headers += _decode_headers(event.headers)
                break

    def _send_response(self, interim=False):
        self._response.finalize()
        cls = h11.InformationalResponse if interim else h11.Response
        self._handler.send_event(cls(
            status_code=self._response.status_code,
            reason=force_bytes(self._response.reason),
            headers=_encode_headers(self._response.raw_headers),
        ))

    def _send_body(self):
        if self._response.body:
            self.chunk(self._response.body)
        self._handler.send_event(h11.EndOfMessage(
            headers=_encode_headers(self._response.raw_headers),
        ))

    method = property(lambda self: self.request.method)
    target = property(lambda self: self.request.target)
    path = property(lambda self: self.request.path)

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
        self._response.body = force_bytes(data, 'utf-8')

    def chunk(self, data):
        self.flush(body_too=False)
        self._response.body = None          # So that `_send_body` skips it
        # Responses to HEAD can't have a message body. We magically skip
        # sending data in that case, so the user doesn't have to remember.
        # (204 and 304 responses also can't have a body, but those have to be
        # explicitly selected by the user, so it's their problem.)
        if self.method != 'HEAD':
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
        self._response = forward(self.request, hostname, port, target, tls)

    def text(self, content):
        self.header('Content-Type', 'text/plain')
        self.body(content)

    def error(self, code):
        self.status(code)
        self.text('Error! %s\r\n' % turq.util.http.error_explanation(code))


class Request:

    def __init__(self, context, method, target, http_version, headers):
        self._context = context
        self.method = method
        self.path = self.target = target
        self.version = self.http_version = http_version
        self.raw_headers = headers
        self.headers = wsgiref.headers.Headers(self.raw_headers)
        self._body = None

    @property
    def body(self):
        # Request body is received lazily. This allows handling
        # finer aspects of the protocol, such as ``Expect: 100-continue``.
        if self._body is None:
            self._context._receive_body()
        return self._body


class Response:

    def __init__(self):
        self.status_code = 200
        self.reason = None
        self.raw_headers = []
        self.headers = wsgiref.headers.Headers(self.raw_headers)
        self.body = b''

    def finalize(self):
        # h11 sends an empty reason phrase by default. While this is
        # correct with regard to the protocol, I think it will be
        # more convenient and less surprising to the user if we fill it.
        if self.reason is None:
            self.reason = turq.util.http.default_reason(self.status_code)

        # RFC 7231 Section 7.1.1.2 requires a ``Date`` header
        # on all 2xx, 3xx, and 4xx responses.
        if 200 <= self.status_code <= 499 and 'Date' not in self.headers:
            self.headers['Date'] = turq.util.http.date()


def _decode_headers(headers):
    # Header values can contain arbitrary bytes. Decode them from ISO-8859-1,
    # which is the historical encoding of HTTP. Decoding bytes from ISO-8859-1
    # is a lossless operation, it cannot fail.
    return [(name.decode(), value.decode('iso-8859-1'))
            for (name, value) in headers]

def _encode_headers(headers):
    return [(force_bytes(name), force_bytes(value))
            for (name, value) in headers]


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
                response.status_code = event.status_code
                # Reason phrases can contain arbitrary bytes.
                # See above regarding ISO-8859-1.
                response.reason = event.reason.decode('iso-8859-1')
                response.raw_headers[:] = _forward_headers(
                    _decode_headers(event.headers),
                    event.http_version.decode())
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

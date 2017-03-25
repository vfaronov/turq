# pylint: disable=protected-access

import contextlib
import wsgiref.headers

import h11

import turq.util.http
import turq.util.logging
from turq.util.text import force_bytes


class RulesContext:

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
        if self._handler.their_state is h11.SEND_BODY:
            self._receive_body()
        self.flush()

    def _build_scope(self):
        scope = {name: getattr(self, name)
                 for name in dir(self) if not name.startswith('_')}
        # Shortcuts for common request methods
        for method in turq.util.http.KNOWN_METHODS:
            scope[method.replace('-', '_')] = (self.method == method)
        return scope

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
    path = property(lambda self: self.request.path)

    def status(self, code, reason=None):
        self._response.status_code = code
        self._response.reason = reason

    def header(self, name, value):
        self._response.headers[name] = value

    def add_header(self, name, value):
        self._response.headers.add_header(name, value)

    def body(self, data):
        self._response.body = force_bytes(data, 'utf-8')

    def chunk(self, data):
        self.flush(body=False)
        self._response.body = None
        if self.method != 'HEAD':
            self._handler.send_event(h11.Data(data=force_bytes(data)))

    def framing(self, content_length=None, keep_alive=None):
        if content_length is not None:
            self._response.use_content_length = content_length
        if keep_alive is not None:
            self._response.keep_alive = keep_alive

    @contextlib.contextmanager
    def interim(self):
        main_response = self._response
        self._response = Response()
        self.status(100)
        yield
        self._send_response(interim=True)
        self._response = main_response

    def flush(self, body=True):
        if self._handler.our_state is h11.SEND_RESPONSE:
            self._send_response()
            # Clear the list of response headers: from this point on,
            # any headers added will be sent in the trailer part.
            self._response.raw_headers[:] = []
        if body and self._handler.our_state is h11.SEND_BODY:
            self._send_body()


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
        self.use_content_length = False
        self.keep_alive = True

    def finalize(self):
        if self.reason is None:
            self.reason = turq.util.http.default_reason(self.status_code)
        if 200 <= self.status_code <= 499 and 'Date' not in self.headers:
            self.headers['Date'] = turq.util.http.date()
        if self.use_content_length:
            self.headers['Content-Length'] = str(len(self.body))
        if not self.keep_alive:
            self.headers.add_header('Connection', 'close')


def _decode_headers(headers):
    return [(name.decode(), value.decode('iso-8859-1'))
            for (name, value) in headers]

def _encode_headers(headers):
    return [(force_bytes(name), force_bytes(value))
            for (name, value) in headers]

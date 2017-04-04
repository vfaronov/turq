# pylint: disable=unused-argument

import base64
import hashlib
import html
import mimetypes
import os
import pkgutil
import posixpath
import socket
import socketserver
import string
import threading
import wsgiref.simple_server

import falcon
import werkzeug.formparser

import turq.examples
from turq.util.http import guess_external_url


STATIC_PREFIX = '/static/'


def make_server(host, port, ipv6, password, mock_server):
    editor = falcon.API(media_type='text/plain; charset=utf-8',
                        middleware=[CommonHeaders()])
    # Microsoft Edge doesn't send ``Authorization: Digest`` to ``/``.
    # Can be circumvented with ``/?``, but I think ``/editor`` is better.
    editor.add_route('/editor', EditorResource(mock_server, password))
    editor.add_route('/', RedirectResource())
    editor.add_sink(static_file, STATIC_PREFIX)
    editor.set_error_serializer(text_error_serializer)
    return wsgiref.simple_server.make_server(
        host, port, editor,
        IPv6EditorServer if ipv6 else EditorServer,
        EditorHandler)


def text_error_serializer(req, resp, exc):
    resp.body = exc.title


class EditorServer(socketserver.ThreadingMixIn,
                   wsgiref.simple_server.WSGIServer):

    address_family = socket.AF_INET
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Do not print tracebacks.
        pass


class IPv6EditorServer(EditorServer):

    address_family = socket.AF_INET6


class EditorHandler(wsgiref.simple_server.WSGIRequestHandler):

    def log_message(self, *args):       # Do not log requests and responses.
        pass


class EditorResource:

    realm = 'Turq editor'
    template = string.Template(
        pkgutil.get_data('turq', 'editor/editor.html.tpl').decode('utf-8'))

    def __init__(self, mock_server, password):
        self.mock_server = mock_server
        self.password = password
        self.nonce = self.new_nonce()
        self._lock = threading.Lock()

    def on_get(self, req, resp):
        self.check_auth(req)
        resp.content_type = 'text/html; charset=utf-8'
        (mock_host, mock_port, *_) = self.mock_server.server_address
        resp.body = self.template.substitute(
            mock_host=html.escape(mock_host), mock_port=mock_port,
            mock_url=html.escape(guess_external_url(mock_host, mock_port)),
            rules=html.escape(self.mock_server.rules),
            examples=turq.examples.load_html(initial_header_level=3))

    def on_post(self, req, resp):
        self.check_auth(req)
        # Need `werkzeug.formparser` because JavaScript sends ``FormData``,
        # which is encoded as multipart.
        (_, form, _) = werkzeug.formparser.parse_form_data(req.env)
        if 'rules' not in form:
            raise falcon.HTTPBadRequest('Bad form')
        try:
            self.mock_server.install_rules(form['rules'])
        except SyntaxError as exc:
            resp.status = falcon.HTTP_422   # Unprocessable Entity
            resp.body = str(exc)
        else:
            resp.status = falcon.HTTP_303   # See Other
            resp.location = '/editor'
            resp.body = 'Rules installed successfully.'

    # We use HTTP digest authentication here, which provides a fairly high
    # level of protection. We use only one-time nonces, so replay attacks
    # should not be possible. An active man-in-the-middle could still intercept
    # a request and substitute their own rules; the ``auth-int`` option
    # is supposed to protect against that, but Chrome and Firefox (at least)
    # don't seem to support it.

    def check_auth(self, req):
        if not self.password:
            return
        auth = werkzeug.http.parse_authorization_header(req.auth)
        password_ok = False
        if self.check_password(req, auth):
            password_ok = True
            with self._lock:
                if auth.nonce == self.nonce:
                    self.nonce = self.new_nonce()
                    return
        raise falcon.HTTPUnauthorized(headers={
            'WWW-Authenticate':
                'Digest realm="%s", qop="auth", charset=UTF-8, '
                'nonce="%s", stale=%s' %
                (self.realm, self.nonce, 'true' if password_ok else 'false')})

    def check_password(self, req, auth):
        if not auth:
            return False
        a1 = '%s:%s:%s' % (auth.username, self.realm, self.password)
        a2 = '%s:%s' % (req.method, auth.uri)
        response = self.h('%s:%s:%s:%s:%s:%s' % (self.h(a1),
                                                 auth.nonce, auth.nc,
                                                 auth.cnonce, auth.qop,
                                                 self.h(a2)))
        return auth.response == response

    @staticmethod
    def h(s):               # pylint: disable=invalid-name
        return hashlib.md5(s.encode('utf-8')).hexdigest().lower()

    @staticmethod
    def new_nonce():
        return base64.b64encode(os.urandom(18)).decode()


class RedirectResource:

    def on_get(self, req, resp):
        raise falcon.HTTPFound('/editor')

    on_post = on_get


def static_file(req, resp):
    path = '/' + req.path[len(STATIC_PREFIX):]
    path = posixpath.normpath(path.replace('\\', '/'))   # Avoid path traversal
    try:
        resp.data = pkgutil.get_data('turq', 'editor%s' % path)
    except FileNotFoundError:
        raise falcon.HTTPNotFound()
    else:
        (resp.content_type, _) = mimetypes.guess_type(path)


class CommonHeaders:

    def process_response(self, req, resp, resource, req_succeeded):
        # This server is very volatile: who knows what will be listening
        # on this host and port tomorrow? So, disable caching completely.
        # We don't want Chrome to "Show saved copy" when Turq is down, etc.
        resp.cache_control = ['no-store']

        # For some reason, under some circumstances, Internet Explorer 11
        # falls back to IE 7 compatibility mode on the Turq editor.
        resp.append_header('X-UA-Compatible', 'IE=edge')

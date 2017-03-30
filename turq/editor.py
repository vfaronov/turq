# pylint: disable=unused-argument

import html
import logging
import pkgutil
import socket
import socketserver
import string
import threading
import wsgiref.simple_server

import falcon
import werkzeug.formparser

import turq.examples
from turq.util.falcon import DisableCache


def make_server(hostname, port, ipv6, mock_server):
    # This server is very volatile: who knows what will be listening on this
    # host and port tomorrow? So, disable caching completely. We don't want
    # e.g. Chrome to prompt to "Show saved copy" when Turq is not running, etc.
    middleware = [DisableCache()]
    editor = falcon.API(media_type='text/plain; charset=utf-8',
                        middleware=middleware)
    editor.add_route('/', RootResource(mock_server))
    editor.set_error_serializer(text_error_serializer)
    return wsgiref.simple_server.make_server(
        hostname, port, editor,
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


class RootResource:

    template = string.Template(
        pkgutil.get_data('turq', 'editor/editor.html.tpl').decode('utf-8'))

    def __init__(self, mock_server):
        self.mock_server = mock_server

    def on_get(self, req, resp):
        resp.content_type = 'text/html; charset=utf-8'
        (hostname, port) = self.mock_server.server_address
        resp.body = self.template.substitute(
            hostname=html.escape(hostname), port=port,
            rules=html.escape(self.mock_server.rules),
            examples=turq.examples.load_html(initial_header_level=3))

    def on_post(self, req, resp):
        (_, form, _) = werkzeug.formparser.parse_form_data(req.env)
        if form.get('do') == 'Shutdown':
            self.do_shutdown(resp)
        elif 'rules' in form:
            self.do_install(form['rules'], resp)
        else:
            raise falcon.HTTPBadRequest('Bad form')

    def do_shutdown(self, resp):
        resp.status = falcon.HTTP_202   # Accepted
        resp.body = 'Turq will now shut down.'
        logging.getLogger('turq').info('shutting down per user request')
        # Shutting down the mock server will cause `serve_forever` to return
        # on the main thread, which will proceed to shut down the editor server
        # and terminate, at which point the thread serving this request will
        # die because it's a daemon thread. This is a race that could prevent
        # the response from being delivered to the client. But I think it is
        # narrow enough in practice.
        threading.Thread(target=self.mock_server.shutdown).start()

    def do_install(self, rules, resp):
        try:
            self.mock_server.install_rules(rules)
        except SyntaxError as exc:
            resp.status = falcon.HTTP_422   # Unprocessable Entity
            resp.body = str(exc)
        else:
            resp.status = falcon.HTTP_303   # See Other
            resp.location = '/'
            resp.body = 'Rules installed successfully.'

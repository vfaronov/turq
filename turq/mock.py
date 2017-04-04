# This module, together with `turq.rules`, constitutes the Turq mock server.
# It tries to be mostly HTTP-compliant by default, but it doesn't care at all
# about performance. In particular, there are no explicit timeouts.

import logging
import socket
import socketserver

import h11

from turq.rules import RULES_FILENAME, RulesContext
import turq.util.http
from turq.util.logging import getNextLogger


class MockServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    allow_reuse_address = True    # Prevent "Address already in use" on restart
    daemon_threads = True

    def __init__(self, host, port, ipv6, initial_rules,
                 bind_and_activate=True):
        self.address_family = socket.AF_INET6 if ipv6 else socket.AF_INET
        super().__init__((host, port), MockHandler, bind_and_activate)
        self.install_rules(initial_rules)

    def install_rules(self, rules):
        self.compiled_rules = compile(rules, RULES_FILENAME, 'exec')
        self.rules = rules
        logging.getLogger('turq').info('new rules installed')


class MockHandler(socketserver.StreamRequestHandler):

    def setup(self):
        super().setup()
        self._logger = getNextLogger('turq.connection')
        self._socket = self.request    # To reduce confusion with HTTP requests
        self._hconn = h11.Connection(our_role=h11.SERVER)

    def handle(self):
        self._logger.info('new connection from %s', self.client_address[0])
        try:
            while True:
                # pylint: disable=protected-access
                event = self.receive_event()
                if isinstance(event, h11.Request):     # not `ConnectionClosed`
                    # `RulesContext` takes care of handling one complete
                    # request/response cycle.
                    RulesContext(self.server.compiled_rules, self)._run(event)
                self._logger.debug('states: %r', self._hconn.states)
                if self._hconn.states == {h11.CLIENT: h11.DONE,
                                          h11.SERVER: h11.DONE}:
                    # Connection persists, proceed to the next cycle.
                    self._hconn.start_next_cycle()
                else:
                    # Connection has to be closed (e.g. because HTTP/1.0
                    # or because somebody sent "Connection: close").
                    break
        except Exception as e:
            self._logger.error('error: %s', e)
            self._logger.debug('states: %r', self._hconn.states)
            if self._hconn.our_state in [h11.SEND_RESPONSE, h11.IDLE]:
                self._send_fatal_error(e)

    @property
    def our_state(self):
        return self._hconn.our_state

    @property
    def their_state(self):
        return self._hconn.their_state

    def receive_event(self):
        while True:
            event = self._hconn.next_event()
            if event is h11.NEED_DATA:
                self._hconn.receive_data(self._socket.recv(4096))
            else:
                return event

    def send_event(self, event):
        data = self._hconn.send(event)
        self._socket.sendall(data)

    def send_raw(self, data):
        self._socket.sendall(data)

    def _send_fatal_error(self, exc):
        status_code = getattr(exc, 'error_status_hint', 500)
        self._logger.debug('sending error response, status %d', status_code)
        try:
            self.send_event(h11.Response(
                status_code=status_code,
                reason=turq.util.http.default_reason(status_code).encode(),
                headers=[
                    (b'Date', turq.util.http.date().encode()),
                    (b'Content-Type', b'text/plain'),
                    (b'Connection', b'close'),
                ],
            ))
            self.send_event(h11.Data(data=('Error: %s\r\n' % exc).encode()))
            self.send_event(h11.EndOfMessage())
        except Exception as e:
            self._logger.debug('cannot send error response: %s', e)

        # A crude way to avoid the TCP reset problem (RFC 7230 Section 6.6).
        try:
            self._socket.shutdown(socket.SHUT_WR)
            while self._socket.recv(1024):
                self._logger.debug('discarding data from client')
        except OSError:     # The client may have already closed the connection
            pass

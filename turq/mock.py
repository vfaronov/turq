import socketserver

import h11

from turq.rules import RulesContext
import turq.util.http
import turq.util.logging


class MockServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, initial_rules, bind_and_activate=True):
        super().__init__(server_address, MockHandler, bind_and_activate)
        self._logger = turq.util.logging.instanceLogger(self)
        self.set_rules(initial_rules)

    def set_rules(self, rules):
        self.rules = rules
        self._logger.info('new rules installed')


class MockHandler(socketserver.StreamRequestHandler):


    def setup(self):
        super().setup()
        self._logger = turq.util.logging.instanceLogger(self)
        self._socket = self.request    # To reduce confusion with HTTP requests
        self._hconn = h11.Connection(our_role=h11.SERVER)

    def handle(self):
        try:
            while True:
                # pylint: disable=protected-access
                RulesContext(self.server.rules, self)._run()
                if self._hconn.states == {h11.CLIENT: h11.DONE,
                                          h11.SERVER: h11.DONE}:
                    # Persistent connection, proceed to next request.
                    self._hconn.start_next_cycle()
                else:
                    break
        except Exception as e:
            self._logger.error('error in request cycle: %s', e)
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
                self._logger.debug('received %r', event)
                return event

    def send_event(self, event):
        self._logger.debug('sending %r', event)
        data = self._hconn.send(event)
        self._socket.sendall(data)

    def _send_fatal_error(self, exc):
        if isinstance(exc, h11.RemoteProtocolError):
            status_code = exc.error_status_hint
        else:
            status_code = 500
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
            self._logger.error('cannot send error response: %s', e)

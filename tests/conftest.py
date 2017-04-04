import socket
import subprocess
import sys
import time

import h11
import pytest
import requests


@pytest.fixture
def turq_instance():
    return TurqInstance()


class TurqInstance:

    """Spins up and controls a live instance of Turq for testing."""

    def __init__(self):
        self.host = 'localhost'
        # Test instance listens on port 13095 instead of the default 13085,
        # to make it easier to run tests while also testing Turq manually.
        # Of course, ideally it should be a random free port instead.
        self.mock_port = 13095
        self.editor_port = 13096
        self.password = ''
        self.extra_args = []
        self.wait = True
        self._process = None
        self.console_output = None

    def __enter__(self):
        args = [sys.executable, '-m', 'turq.main',
                '--bind', self.host, '--mock-port', str(self.mock_port),
                '--editor-port', str(self.editor_port)]
        if self.password is not None:
            args += ['--editor-password', self.password]
        args += self.extra_args
        self._process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.PIPE)
        if self.wait:
            self._wait_for_server()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._process.terminate()
        self._process.wait()
        self.console_output = self._process.stderr.read().decode()
        return False

    def _wait_for_server(self, timeout=3):
        # Wait until the mock server starts accepting connections,
        # but no more than `timeout` seconds.
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            time.sleep(0.1)
            try:
                self.connect().close()
                self.connect_editor().close()
                return
            except OSError:
                pass
        raise RuntimeError('Turq failed to start')

    def connect(self):
        return socket.create_connection((self.host, self.mock_port), timeout=5)

    def connect_editor(self):
        return socket.create_connection((self.host, self.editor_port),
                                        timeout=5)

    def send(self, *events):
        hconn = h11.Connection(our_role=h11.CLIENT)
        with self.connect() as sock:
            for event in events:
                sock.sendall(hconn.send(event))
            sock.shutdown(socket.SHUT_WR)
            while hconn.their_state is not h11.CLOSED:
                event = hconn.next_event()
                if event is h11.NEED_DATA:
                    hconn.receive_data(sock.recv(4096))
                elif not isinstance(event, h11.ConnectionClosed):
                    yield event

    def request(self, method, url, **kwargs):
        full_url = 'http://%s:%d%s' % (self.host, self.mock_port, url)
        return requests.request(method, full_url, **kwargs)

    def request_editor(self, method, url, **kwargs):
        full_url = 'http://%s:%d%s' % (self.host, self.editor_port, url)
        return requests.request(method, full_url, **kwargs)

import socket
import subprocess
import sys
import time

import h11
import pytest


@pytest.fixture
def turq_instance():
    return TurqInstance()


class TurqInstance:

    """Spins up and controls a live instance of Turq for testing."""

    def __init__(self):
        self.mock_hostname = 'localhost'
        self.mock_port = 13085
        self.extra_args = []
        self._process = None

    def __enter__(self):
        args = [sys.executable, '-m', 'turq.main',
                '--mock-bind', self.mock_hostname,
                '--mock-port', str(self.mock_port)] + self.extra_args
        self._process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        self._wait_for_server()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._process.terminate()
        self._process.wait()
        return False

    def _wait_for_server(self, timeout=3):
        # Wait until the mock server starts accepting connections,
        # but no more than `timeout` seconds.
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            time.sleep(0.1)
            try:
                self.connect().close()
                return
            except OSError:
                pass
        raise RuntimeError('Turq failed to start')

    def connect(self):
        return socket.create_connection((self.mock_hostname, self.mock_port),
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

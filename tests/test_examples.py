# Test the examples from the Turq documentation (``turq/examples.rst``).
# Every test function is matched (by function name) to exactly one
# snippet of example code, which is loaded into Turq by the `example` fixture.

# pylint: disable=redefined-outer-name,invalid-name

import json
import time

import h11
import pytest

import turq.examples

examples = turq.examples.load_pairs()


@pytest.fixture
def example(request, turq_instance, tmpdir):
    test_name = request.node.name
    [example_code] = [code for (slug, code) in examples if slug in test_name]
    rules_path = tmpdir.join('rules.py')
    rules_path.write(example_code)
    turq_instance.extra_args = ['-r', str(rules_path)]
    with turq_instance:
        yield turq_instance


def test_basics_1_ok(example):
    resp, data, _ = example.send(h11.Request(method='GET', target='/hello',
                                             headers=[('Host', 'example')]),
                                 h11.EndOfMessage())
    assert resp.status_code == 200
    assert resp.reason == b'OK'
    assert (b'content-type', b'text/plain') in resp.headers
    assert data.data == b'Hello world!\r\n'


def test_basics_1_not_found(example):
    resp, data, _ = example.send(h11.Request(method='GET', target='/',
                                             headers=[('Host', 'example')]),
                                 h11.EndOfMessage())
    assert resp.status_code == 404
    assert resp.reason == b'Not Found'
    assert (b'content-type', b'text/plain') in resp.headers
    assert b'Error! ' in data.data


def test_basics_1_head(example):
    resp, _ = example.send(h11.Request(method='HEAD', target='/hello',
                                       headers=[('Host', 'example')]),
                           h11.EndOfMessage())
    assert resp.status_code == 200
    assert resp.reason == b'OK'
    assert (b'content-type', b'text/plain') in resp.headers


def test_basics_1_client_error(example):
    # Request a URL that is too long for h11's buffers.
    resp, data, _ = example.send(h11.Request(method='GET', target='/a' * 99999,
                                             headers=[('Host', 'example')]),
                                 h11.EndOfMessage())
    assert 400 <= resp.status_code <= 499
    assert resp.reason
    assert (b'content-type', b'text/plain') in resp.headers
    assert b'Error: ' in data.data


def test_basics_1_pipelining(example):
    with example.connect() as sock:
        # Send three requests in a row...
        sock.sendall(b'GET /hello HTTP/1.1\r\nHost: example\r\n\r\n' * 3)
        # ...and then read the three responses.
        n = 0
        while n < 3:
            n += sock.recv(4096).count(b'HTTP/1.1 200 OK\r\n')


def test_response_headers_1(example):
    resp, _ = example.send(h11.Request(method='GET', target='/',
                                       headers=[('Host', 'example')]),
                           h11.EndOfMessage())
    assert (b'cache-control', b'max-age=3600') in resp.headers
    assert (b'cache-control', b'public') not in resp.headers


def test_response_headers_2(example):
    resp, _ = example.send(h11.Request(method='GET', target='/',
                                       headers=[('Host', 'example')]),
                           h11.EndOfMessage())
    assert (b'set-cookie', b'sessionid=123456') in resp.headers
    assert (b'set-cookie', b'__adtrack=abcdef') in resp.headers


def test_custom_status_code_and_reason_1(example):
    resp, _, _ = example.send(h11.Request(method='GET', target='/',
                                          headers=[('Host', 'example')]),
                              h11.EndOfMessage())
    assert resp.status_code == 567
    assert resp.reason == b'Server Fell Over'


def test_response_framing_1_content_length(example):
    resp, data, _ = example.send(h11.Request(method='GET', target='/',
                                             headers=[('Host', 'example')]),
                                 h11.EndOfMessage())
    assert (b'content-length', b'14') in resp.headers
    assert b'transfer-encoding' not in dict(resp.headers)
    assert data.data == b'Hello world!\r\n'


def test_response_framing_1_keep_alive(example):
    with example.connect() as sock:
        for _ in range(3):      # The same socket can be reused multiple times.
            sock.sendall(b'GET / HTTP/1.1\r\n'
                         b'Host: example\r\n'
                         b'\r\n')
            while b'HTTP/1.1 200 OK\r\n' not in sock.recv(4096):
                pass


def test_response_framing_1_http10(example):
    with example.connect() as sock:
        sock.sendall(b'GET / HTTP/1.0\r\n'
                     b'\r\n')
        time.sleep(1)
        assert b'HTTP/1.1 200 OK\r\n' in sock.recv(4096)
        assert sock.recv(4096) == b''       # Server closed the connection


def test_response_framing_2_close(example):
    with example.connect() as sock:
        sock.sendall(b'GET / HTTP/1.1\r\n'
                     b'Host: example\r\n'
                     b'\r\n')
        time.sleep(1)
        assert b'HTTP/1.1 200 OK\r\n' in sock.recv(4096)
        assert sock.recv(4096) == b''       # Server closed the connection


def test_streaming_responses_1(example):
    t0 = time.monotonic()
    resp, data1, data2, data3, _ = example.send(
        h11.Request(method='GET', target='/', headers=[('Host', 'example')]),
        h11.EndOfMessage())
    t1 = time.monotonic()
    assert t1 - t0 >= 3     # At least 3 seconds elapsed, due to ``sleep()``
    assert (b'content-type', b'text/event-stream') in resp.headers
    assert data1.data == b'data: my event 1\r\n\r\n'
    assert data2.data == b'data: my event 2\r\n\r\n'
    assert data3.data == b'data: my event 3\r\n\r\n'


def test_streaming_responses_2(example):
    resp, data1, data2, end = example.send(
        h11.Request(method='GET', target='/', headers=[('Host', 'example')]),
        h11.EndOfMessage())
    assert (b'content-type', b'text/plain') in resp.headers
    assert b'content-md5' not in dict(resp.headers)
    assert data1.data == b'Hello, '
    assert data2.data == b'world!\n'
    assert b'content-md5' in dict(end.headers)      # In the trailer part


def test_handling_expect_100_continue_1(example):
    with example.connect() as sock:
        sock.sendall(b'POST / HTTP/1.1\r\n'
                     b'Host: example\r\n'
                     b'Content-Length: 14\r\n'
                     b'\r\n')
        assert b'HTTP/1.1 100 Continue\r\n' in sock.recv(4096)
        sock.sendall(b'Hello world!\r\n')
        assert b'HTTP/1.1 200 OK\r\n' in sock.recv(4096)


def test_handling_expect_100_continue_2(example):
    with example.connect() as sock:
        sock.sendall(b'POST / HTTP/1.1\r\n'
                     b'Host: example\r\n'
                     b'Content-Length: 14\r\n'
                     b'\r\n')
        assert b'HTTP/1.1 403 Forbidden\r\n' in sock.recv(4096)


def test_forwarding_requests_1(example):
    resp, data, _ = example.send(
        h11.Request(method='GET', target='/get',
                    headers=[('Host', 'example'),
                             ('User-Agent', 'test'),
                             ('Upgrade', 'my-protocol'),
                             ('Connection', 'upgrade')]),
        h11.EndOfMessage())
    assert (b'content-type', b'application/json') in resp.headers
    assert (b'cache-control', b'max-age=86400') in resp.headers
    # Headers were correctly forwarded by Turq.
    what_upstream_saw = json.loads(data.data.decode('utf-8'))
    assert 'Upgrade' not in what_upstream_saw['headers']
    assert what_upstream_saw['headers']['User-Agent'] == 'test'
    # Unfortunately httpbin does not reflect ``Via`` in ``headers``.


def test_forwarding_requests_2(example):
    resp, _, _ = example.send(h11.Request(method='GET', target='/',
                                          headers=[('Host', 'example')]),
                              h11.EndOfMessage())
    # ``develop1.example`` is unreachable
    assert 500 <= resp.status_code <= 599

Examples
========

Basics
------

::

    if path == '/hello':
        header('Content-Type', 'text/plain')
        body('Hello world!\r\n')
    else:
        error(404)


Response headers
----------------

``header()`` *replaces* the given header, so this will send
**only** ``max-age``::

    header('Cache-Control', 'public')
    header('Cache-Control', 'max-age=3600')

To *add* a header instead::

    add_header('Set-Cookie', 'sessionid=123456')
    add_header('Set-Cookie', '__adtrack=abcdef')


Response framing
----------------

By default, if the client supports it, Turq uses ``Transfer-Encoding: chunked``
and keeps the connection alive.

To use ``Content-Length`` instead of ``Transfer-Encoding``,
call ``content_length()`` after you've set the body::

    text('Hello world!\r\n')
    content_length()

To close the connection after sending the response::

    add_header('Connection', 'close')
    text('Hello world!\r\n')


Streaming responses
-------------------

::

    header('Content-Type', 'text/event-stream')
    sleep(1)        # 1 second delay
    chunk('- data: my event 1\r\n\r\n')
    sleep(1)
    chunk('- data: my event 2\r\n\r\n')
    sleep(1)
    chunk('- data: my event 3\r\n\r\n')

Once you call ``chunk()``, the response begins streaming.
Any headers you set after that will be sent in the `trailer part`_::

    header('Content-Type', 'text/plain')
    chunk('Hello, ')
    chunk('world!\n')
    header('Content-MD5', '746308829575e17c3331bbcb00c0898b')

.. _trailer part: https://tools.ietf.org/html/rfc7230#section-4.1.2


Custom status code and reason
-----------------------------

::

    status(567, 'Server Fell Over')
    text('Server crashed, sorry!\r\n')

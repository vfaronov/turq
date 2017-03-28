Examples
========

Basics
------

::

    # This is a comment. Normal Python syntax.
    if path == '/hello':
        header('Content-Type', 'text/plain')
        body('Hello world!\r\n')
    else:
        error(404)


Request details
---------------

::

    if request.json:     # parsed JSON body
        name = request.json['name']
    elif request.form:   # URL-encoded or multipart
        name = request.form['name']
    elif query:     # query string parameters
        name = query['name']
    else:
        raw_name = request.body     # raw bytes
        name = raw_name.decode('utf-8')

    # Header names are case-insensitive
    if 'json' in request.headers['Accept']:
        json({'hello': name})
    else:
        text('Hello %s!\r\n' % name)


Response headers
----------------

``header()`` *replaces* the given header, so this will send
**only** ``max-age``::

    header('Cache-Control', 'public')
    header('Cache-Control', 'max-age=3600')

To *add* a header instead::

    add_header('Set-Cookie', 'sessionid=123456')
    add_header('Set-Cookie', '__adtrack=abcdef')


Custom status code and reason
-----------------------------

::

    status(567, 'Server Fell Over')
    text('Server crashed, sorry!\r\n')


Forwarding requests
-------------------

Turq can act as a gateway or “reverse proxy”::

    forward('httpbin.org', 80,  # host, port
            target)             # path + query string
    # At this point, response from httpbin.org:80
    # has been copied to Turq, and can be tweaked:
    delete_header('Server')
    add_header('Cache-Control', 'max-age=86400')

Turq uses TLS when connecting to port 443, but **ignores certificates**.
You can override TLS like this::

    forward('develop1.example', 8765,
            '/v1/articles', tls=True)


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
    chunk('data: my event 1\r\n\r\n')
    sleep(1)
    chunk('data: my event 2\r\n\r\n')
    sleep(1)
    chunk('data: my event 3\r\n\r\n')

Once you call ``chunk()``, the response begins streaming.
Any headers you set after that will be sent in the `trailer part`_::

    header('Content-Type', 'text/plain')
    chunk('Hello, ')
    chunk('world!\n')
    header('Content-MD5', '746308829575e17c3331bbcb00c0898b')

.. _trailer part: https://tools.ietf.org/html/rfc7230#section-4.1.2


Handling ``Expect: 100-continue``
---------------------------------

::

    with interim():
        status(100)

    text('Resource updated OK')

In the above example, `100 (Continue)`_ is sent immediately after the
``interim()`` block, but the final 200 (OK) response is sent only after
reading the full request body.

If instead you want to send a response *before* reading the request body::

    error(403)      # Forbidden
    flush()

.. _100 (Continue): https://tools.ietf.org/html/rfc7231#section-6.2.1

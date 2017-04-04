User guide
==========

.. highlight:: console

Quick start
-----------

To run Turq, you need `Python`_ 3.4 or higher.
Once you have that, install Turq with `pip`_::

    $ pip3 install turq

Start Turq::

    $ turq

You should see something like this::

    18:22:19  turq  new rules installed
    18:22:19  turq  mock on port 13085 - try http://pergamon:13085/
    18:22:19  turq  editor on port 13086 - try http://pergamon:13086/
    18:22:19  turq  editor password: QGOf9Y9Eqjvz4XhY4JA3U7hG (any username)

As you can see, by default, Turq starts two TCP servers.
One is the *mock server*, which serves the actual mocks you define.
The other is the optional *rules editor*, which makes writing mocks easier.

The first thing you want to do is probably to open the editor.
By default, Turq listens on all network interfaces, so you can open the editor
at ``http://localhost:13086/`` in your Web browser. Turq also tries to guess
and print a URL that doesn't include ``localhost``, which is useful when
you run Turq on some remote machine via SSH.

Turq will ask you to enter a password that it generated and printed for you.
You can leave the username field blank, it is ignored.

.. warning::

   Anybody with access to the Turq editor can **execute arbitrary code**
   in the Turq process. The default password protection should keep you safe
   in most cases, but doesn't help against an active man-in-the-middle.
   If that's a problem, limit Turq to loopback with ``--bind localhost``,
   or `run without the editor <Programmatic use_>`_.

The editor should be self-explanatory: you define your mock by writing
code in the big code area, using the examples on the left as your guide.
The default rules are just ``error(404)``, which means that the mock server
will respond with 404 (Not Found) to any request it gets. Let's check that
using curl::

    $ curl -i http://pergamon:13085/some/page.html
    HTTP/1.1 404 Not Found
    content-type: text/plain; charset=utf-8
    date: Tue, 04 Apr 2017 15:33:55 GMT
    transfer-encoding: chunked

    Error! Nothing matches the given URI

Keep an eye on the system console where you launched ``turq`` ---
a log of all requests and responses is printed there::

    19:01:30  turq.connection.1  new connection from 127.0.0.1
    19:01:30  turq.request.1  > GET /some/page.html HTTP/1.1
    19:01:30  turq.request.1  < HTTP/1.1 404 Not Found

When you are done, stop Turq by pressing Ctrl+C in the console.

That's it, basically. Check ``turq --help`` for command-line options,
or read on for more hints on how to use Turq.

.. _Python: https://www.python.org/
.. _pip: https://pip.pypa.io/en/stable/


Programmatic use
----------------

Turq was designed for interactive use; it trades precision for convenience
and simplicity. However, you can use it non-interactively if you like::

    $ turq --no-editor --rules /path/to/rules.py

Give it a second to spin up, or just loop until you can ``connect()`` to it.
Shut it down with SIGTERM like any other process::

    $ pkill turq

It goes without saying that Turq can’t be used anywhere near production.


Using mitmproxy with Turq
-------------------------

Put `mitmproxy`_ in front of Turq to:

- enable TLS (``https``) access to the mock server;
- inspect all requests and responses in detail;
- validate them with `HTTPolice`_; and more.

.. _mitmproxy: https://mitmproxy.org/
.. _HTTPolice: https://github.com/vfaronov/httpolice

Assuming Turq runs on the default port, use a command like this::

    $ mitmproxy --port 13185 --reverse http://localhost:13085

Then tell your client to connect to port 13185 (``http`` or ``https``)
instead of 13085.


Known issues
------------

.. highlight:: python

Password protection in the rules editor does not work well in some browsers.
For example, you may randomly get "Connection error" in Internet Explorer.
To avoid this, you can disable password protection with ``-P ""``, but be sure
to have some other protection instead.

The mock server doesn't send any cache-related headers by default. As a result,
some browsers may decide to cache your mocks, leading to strange results.
You can disable caching in your rules::

    add_header('Cache-Control', 'no-store')

Turq has limited options to control the addresses it listens on. If you want
to do something that you can't accomplish with those options, try using
`socat`_ or mitmproxy to forward ports manually.

.. _socat: http://www.dest-unreach.org/socat/

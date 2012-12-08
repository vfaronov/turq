Turq, the mock HTTP server
==========================

.. highlight:: python

Turq is a small HTTP server that is scriptable in a Python-based DSL.
It is designed for mocking HTTP services quickly and interactively.


Starting Turq
~~~~~~~~~~~~~
First you need to install it, normally from PyPI, for example::

    $ pip install turq

Now you have a Python module called ``turq``, and you can run it with::

    $ python -m turq

This will start Turq on port 13085 by default,
or you can choose another one with the ``-p`` option::

    $ sudo python -m turq -p 80

Assuming your hostname is ``machine.example``, and the port is 13085,
you can now open the Turq console at ``http://machine.example:13085/+turq/``
or just ``http://localhost:13085/+turq/``

The Turq console is where you post the rules that define your mock.
Type in the code and hit “Commit”, and Turq will start serving that.


Rules structure
~~~~~~~~~~~~~~~
The code you post is pure Python code that is not sandboxed,
which means you can import and use any modules if you wish so.

The code is interpreted right away.
It should declare *rules* that will be applied to a matching request.
Currently there is just one type of rule:

.. function:: path(path='*', trailing_slash=True)

This rule will be applied to every request whose path
matches the ``path`` parameter,
with an asterisk ``*`` meaning “zero or more of any characters”.
This is like routing in HTTP frameworks.
The query string is not considered part of the path.

``path('/foo')`` will match a request for ``/foo/``,
but ``path('/foo', trailing_slash=False)`` will not.
A simple ``path()`` matches everything.

The :func:`path` function returns an object
on which you then call methods to fill out your rule,
i.e. how to respond to a matching request.
Most methods can be daisy-chained. For example::

    path('/index.html').html().gzip().expires('1 day')

You can also use a rule as a context manager::

    with path('/index.html') as r:
        r.html()
        r.gzip()
        r.expires('1 day')

Matching rules are applied in the order they appear in your code.
For example, given::

    path().status(200)
    path('/foo/bar/*').status(404)
    path('/foo/*').status(500)

a request for ``/foo/bar/baz`` will result in status 500.


Simple rule elements
~~~~~~~~~~~~~~~~~~~~
.. currentmodule:: turq
.. automethod:: Rule.status
.. automethod:: Rule.header
.. automethod:: Rule.add_header
.. automethod:: Rule.body
.. automethod:: Rule.body_file
.. automethod:: Rule.body_url
.. automethod:: Rule.ctype
.. automethod:: Rule.text
.. automethod:: Rule.lots_of_text
.. automethod:: Rule.html
.. automethod:: Rule.lots_of_html
.. automethod:: Rule.json
.. automethod:: Rule.js
.. automethod:: Rule.xml
.. automethod:: Rule.redirect
.. automethod:: Rule.cookie
.. automethod:: Rule.basic_auth
.. automethod:: Rule.digest_auth
.. automethod:: Rule.allow
.. automethod:: Rule.cors
.. automethod:: Rule.expires
.. automethod:: Rule.gzip

Alternating responses
~~~~~~~~~~~~~~~~~~~~~
Within any rule,
Turq can switch between multiple *sub-rules* for successive requests.
A group of sub-rules is initiated with the :meth:`~Rule.first` call,
which begins the sub-rule for the first request.
You will also have zero or more :meth:`~Rule.next` calls
and zero or one :meth:`~Rule.then` call.
If you have :meth:`~Rule.next` but no :meth:`~Rule.then`,
the cycle will eventually return to :meth:`~Rule.first` and start over.

Easier to explain by example.
Here we alternate between “foo” and “bar”::

    with path('/') as r:
        r.first().text('foo')
        r.next().text('bar')

Here we arrive at “baz” and stay there::

    with path('/') as r:
        r.first().text('foo')
        r.next().text('bar')
        r.then().text('baz')

Rule elements declared outside of
:meth:`~Rule.first`, :meth:`~Rule.next` and :meth:`~Rule.then`
will be applied to every response.
For example, here, we send a custom ``Server`` header with every response::

    with path('/') as r:
        r.header('Server', 'WonkyHTTPd/1.4.2b')
        r.first().text('foo')
        r.next().text('bar')


Stochastic responses
~~~~~~~~~~~~~~~~~~~~
Whereas :meth:`~Rule.first` et al. are deterministic,
the :meth:`~Rule.maybe` call adds a stochastic dimension to the response.

.. automethod:: Rule.maybe(probability=0.1)
.. automethod:: Rule.otherwise

This can be used to imitate occasional errors::

    with path() as r:
        r.maybe().status(502).text('Bad Gateway')
        r.otherwise().html()

Probabilities don’t have to cover everything::

    with path() as r:
        r.html(text='Welcome to our site!')
        r.maybe(0.01).cookie('evilTracking', '12345')


Parametrized responses
~~~~~~~~~~~~~~~~~~~~~~
Sometimes you need the response to depend on the request.
For example, suppose you have some crawler
that fetches product info
and expects the response to contain the requested product ID.
You can do it easily with Turq::

    path('/products').json(lambda req: {'id': req.query['id']})

Most rule elements that accept a simple value will also accept a function.
The function is called with a :class:`Request` object as the only argument.

.. autoclass:: Request

If you need even more logic,
you can provide a custom handler function,
attaching it to the rule by using the rule as a decorator::

    @path('/products')
    def process(req, r):
        if req.query['id'].startswith('SCR31-'):
            r.status(403).text('access to product info denied')
        else:
            r.json({'id': req.query['id']})


Limitations
~~~~~~~~~~~
Turq does not provide full control over the HTTP exchange on the wire.
For example:

- it always closes the connection after handling one request
  (and for this reason does not send ``Content-Length`` by default);
- the ``Server`` and ``Date`` response headers are always sent
  (but you can override them—in particular, set them to empty strings);
- you cannot change the HTTP version that is sent in the response status line.

If you need to tweak such things,
you might be better off using the good old `netcat`
or writing some custom code.


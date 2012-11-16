Turq is a tool for semi-interactively testing and debugging HTTP clients.
Somewhat like `httpbin <http://httpbin.org/>`_,
but more interactive and flexible.
Turq runs a primitive HTTP server that is scriptable in a Python-based DSL.
You can quickly set up mock URLs
that respond with the status, headers and body of your choosing.

Usage
-----
Grab ``turq.py`` and run this (on a machine with Python 2.6 or 2.7)::

    $ python turq.py 
    Listening on port 35835
    Try http://localhost:35835/+turq/

Open ``http://localhost:35835/+turq/`` in your Web browser.
You should see a text area. This is the Turq console.
Enter this and click “Commit”::

    path('*').text('Hello world!')

Now open ``http://localhost:35835/`` (without the ``+turq/``) in another tab.
You should see a plain-text greeting.

Examples
--------
Redirect from root to an ``index.php``,
which returns a simple HTML page after 2 seconds of “loading”::

    path('/').redirect('/index.php')
    path('/index.php').delay(2).html()

Imitate a JSON API with cross-origin support::

    path('/api/v1/*').cors().json({'result': 123})

Prompt for basic HTTP authentication,
then serve up a simple page (ignoring credentials)::

    with path('/secret') as r:
        r.first().basic_auth()
        r.then().html()

Imitate round-robin balancing between three backends, one of which is slow::
    
    with path('*') as r:
        r.first().html()
        r.next().html()
        r.next().delay(5).html()

Serve XML from ``/news.rss`` on ``GET`` and ``HEAD``,
disallow all other methods::

    @path('/news.rss')
    def process(req, r):
        if req.method in ('GET', 'HEAD'):
            r.xml('<rss></rss>')
        else:
            r.status(405).xml('<error>Method not allowed</error>')


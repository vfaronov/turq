Turq is a tool for semi-interactively testing and debugging HTTP clients.
Somewhat like `httpbin <http://httpbin.org/>`_,
but more interactive and flexible.
Turq runs a small HTTP server that is scriptable in a Python-based DSL.
It lets you quickly set up mock URLs
that respond with the status, headers and body of your choosing.

Usage
-----
Run this on a machine with Python 2.6 or 2.7::

    $ pip install turq
    $ python -m turq
    Listening on port 13085
    Try http://localhost:13085/+turq/

Open ``http://localhost:13085/+turq/`` in your Web browser.
You should see a text area. This is the Turq console.
Enter this and click “Commit”::

    path('*').text()

Now open ``http://localhost:13085/`` (without the ``+turq/``) in another tab.
You should see a plain-text greeting.

Examples
--------
Redirect from root to an ``index.php``,
which returns a simple HTML page after 2 seconds of “loading”::

    path('/').redirect('/index.php')
    path('/index.php').delay(2).html()

Imitate a JSON API with JSONP and cross-origin support::

    path('/api/v1/*').cors().json()

Prompt for basic HTTP authentication,
then serve up a page with some text (ignoring credentials)::

    with path('/secret') as r:
        r.first().basic_auth()
        r.then().lots_of_html()

Imitate round-robin balancing between three backends, one of which is slow::
    
    with path('/') as r:
        r.first().html()
        r.next().html()
        r.next().delay(5).html()

Simulate an intermittent error::

    with path() as r:
        r.maybe().status(502).text('Bad Gateway')
        r.otherwise().html()

Serve XML from ``/product.xml``, reflecting the passed ``id`` parameter::
    
    path('/product.xml').xml(
        lambda req: '<product><id>%s</id></product>' % req.query['id']
    )

For more, see the `complete documentation <https://turq.readthedocs.org/>`_.


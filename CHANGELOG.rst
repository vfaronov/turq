History of changes
==================

Unreleased
----------

- Complete rewrite. Only the most notable changes are listed below.

- Requires Python 3.4 or higher.

- The rules language is completely different, simpler and more powerful.

- Notable new features of the rules language:

  - forwarding to other servers ("reverse proxy");
  - easy "RESTful" routing with path segments;
  - easy construction of arbitrary HTML pages (using `Dominate`_);
  - CORS support now handles preflight requests automatically;
  - control over finer aspects of the protocol: streaming, 1xx responses,
    ``Content-Length``, ``Transfer-Encoding``, keep-alive.

- On the other hand, some features have been removed for now:

  - alternating responses (``first()``, ``next()``, ``then()``);
  - shortcuts for JavaScript and XML responses (``js()``, ``xml()``).

- You can now choose which network interface Turq listens on, including IPv6.

- The Turq editor (formerly known as "console") now has automatic indentation
  and syntax highlighting.

- The Turq editor is now optional, listens on a separate port,
  and is protected with a password by default.

- Turq can now print more information to the (system) console, including
  request and response headers.

- Initial rules may now be read from a file at startup. This provides a simple
  way to use Turq programmatically.

- Turq can now handle multiple concurrent requests.

.. _Dominate: https://github.com/Knio/dominate


0.2.0 - 2012-12-09
------------------

- Stochastic responses (``maybe()``, ``otherwise()``).

- Various features of the response can now be parametrized with lambdas.

- ``body_file()`` now expands tilde to the user's home directory.


0.1.0 - 2012-11-17
------------------

Initial release.

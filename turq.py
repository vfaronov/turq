#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.2.0'

import BaseHTTPServer
from cStringIO import StringIO
from datetime import datetime, timedelta
import email.message
import gzip
import httplib
import json
from optparse import OptionParser
import os.path
import random
import re
import socket
import string
import sys
import time
import traceback
import urllib2
import urlparse


DEFAULT_PORT = 13085

class Request(object):
    
    """An HTTP request.
    
    .. attribute:: method
       
       Request method.
    
    .. attribute:: path
       
       The request path, excluding the query string.
    
    .. attribute:: query
       
       A dictionary of parameters parsed from the query string.
       An empty dictionary if none can be parsed.
    
    .. attribute:: headers
       
       An ``rfc822.Message``-like mapping of request headers.
    
    .. attribute:: body
       
       Request entity body as a `str` if there is one, otherwise `None`.
    """
    
    def __init__(self, method, path, query, headers, body):
        self.method = method
        self.path = path
        self.query = query
        self.headers = headers
        self.body = body
    
    def p(self, x):
        if callable(x):
            return x(self)
        else:
            return x


class Response(object):
    
    def __init__(self):
        self.status = httplib.OK
        self.headers = email.message.Message()
        self.body = None
    
    def set_header(self, name, value, **params):
        del self.headers[name]
        self.headers.add_header(name, value, **params)
    
    def add_header(self, name, value, **params):
        self.headers.add_header(name, value, **params)


def make_text(nbytes):
    buf = StringIO()
    written = 0
    words = 'lorem ipsum dolor sit amet, consectetur adipisicing elit'.split()
    while written < nbytes:
        word = random.choice(words)
        buf.write(word)
        written += len(word)
        if random.random() < 0.01:
            buf.write('\n\n')
            written += 2
        else:
            buf.write(' ')
            written += 1
    return buf.getvalue()


def html_escape(s):
    return s.replace('&', '&amp;').replace('"', '&quot;'). \
             replace('<', '&lt;').replace('>', '&gt;')


class Cheat(object):
    
    items = []
    
    @staticmethod
    def entry(args='', comment=''):
        def decorator(func):
            Cheat.items.append((func.__name__, args, comment))
            return func
        return decorator
    
    @staticmethod
    def format():
        code = (
            '<p><code class="example">path(\'/products/*\').delay(1).html().'
            'cookie(\'sessionid\', \'1234\', max_age=3600)</code></p>'
            '<table><tbody>'
        )
        for name, args, comment in Cheat.items:
            code += (
                '<tr><th><code>%s(<span class="args">%s</span>)</code></th>'
                '<td>%s</td></tr>' % (name, html_escape(args), comment)
            )
        code += '</tbody></table>'
        return code


class Rule(object):
    
    url_cache = {}
    
    def __init__(self):
        self._status = None
        
        # Headers are tricky.
        # We just store a sequence of (operation, name, value, params) tuples,
        # a patch of sorts, and then apply this patch.
        # Operation can be "set" (replacing) or "add".
        self._headers = []
        
        self._body = None
        self._processor = None
        self._delay = None
        self._chain = []
        self._final = None
        self._counter = 0
        self._maybe = []
        self._enable_cors = False
        self._allow = None
        self._gzip = False
    
    @Cheat.entry('code')
    def status(self, code):
        """Set response status to `code`."""
        self._status = code
        return self
    
    @Cheat.entry('name, value, **params', 'params are appended as k=v pairs')
    def header(self, name, value, **params):
        """Set response header `name` to `value`.
        
        If `params` are specified, they are appended as k=v pairs.
        For example::
        
            header('Content-Type', 'text/html', charset='utf-8')
        
        produces::
        
            Content-Type: text/html; charset="utf-8"
        """
        self._headers.append(('set', name, value, params))
        return self
    
    @Cheat.entry('name, value, **params', 'added, not replaced')
    def add_header(self, name, value, **params):
        """Same as :meth:`~Rule.header`, but add the header, not replace it.
        
        This can be used to send multiple headers with the same name,
        such as ``Via`` or ``Set-Cookie``
        (but for the latter see :meth:`~Rule.cookie`).
        """
        self._headers.append(('add', name, value, params))
        return self
    
    @Cheat.entry('data')
    def body(self, data):
        """Set response entity body to `data`."""
        self._body = data
        return self
    
    @Cheat.entry('path')
    def body_file(self, path):
        """Set response entity body to the contents of `path`.
        
        The file at `path` is read when the rules are posted.
        `path` undergoes tilde expansion.
        """
        return self.body(open(os.path.expanduser(path)).read())
    
    @Cheat.entry('url', 'data from <var>url</var> is cached until Turq exits')
    def body_url(self, url):
        """Set response entity body to the contents of `url`.
        
        The resource at `url` is fetched once and cached until Turq exits.
        Note that this method only sets the entity body.
        HTTP status and headers are not copied from `url`.
        """
        if url not in Rule.url_cache:
            Rule.url_cache[url] = urllib2.urlopen(url).read()
        return self.body(Rule.url_cache[url])
    
    @Cheat.entry('seconds')
    def delay(self, seconds):
        """Delay for `seconds` before serving the response."""
        self._delay = seconds
        return self
    
    def __call__(self, proc):
        self._processor = proc
        return proc
    
    @Cheat.entry('mime_type', 'content type')
    def ctype(self, value):
        """Set response ``Content-Type`` to `value`."""
        return self.header('Content-Type', value)
    
    @Cheat.entry('[text]', 'plain text')
    def text(self, text='Hello world!'):
        """Set up a ``text/plain`` response."""
        return self.ctype('text/plain; charset=utf-8').body(text)
    
    @Cheat.entry('[nbytes]', 'roughly <var>nbytes</var> of plain text')
    def lots_of_text(self, nbytes=20000):
        """Set up a ``text/plain`` response with lots of text.
        
        Lines of dummy text will be generated
        so that the entity body is very roughly `nbytes` in length.
        """
        return self.text(make_text(nbytes))
    
    @Cheat.entry('[title], [text]', 'basic HTML page')
    def html(self, title='Hello world!', text='This is Turq!'):
        """Set up a ``text/html`` response.
        
        A basic HTML page with `title` and a paragraph of `text` is served.
        """
        return self.ctype('text/html; charset=utf-8').body(lambda req: (
            '''<!DOCTYPE html>
<html>
    <head>
        <title>%s</title>
    </head>
    <body>
        <h1>%s</h1>
        <p>%s</p>
    </body>
</html>''' % (req.p(title), req.p(title), req.p(text))
        ))
    
    @Cheat.entry('[nbytes]', 'roughly <var>nbytes</var> of HTML')
    def lots_of_html(self, nbytes=20000, title='Hello world!'):
        """Set up a ``text/html`` response with lots of text.
        
        Like :meth:`~Rule.lots_of_text`, but wrapped in HTML paragraphs.
        """
        return self.html(
            title=title,
            text=make_text(nbytes - 100).replace('\n\n', '</p><p>')
        )
    
    @Cheat.entry('[data]',
                 'JSONP is handled automatically, '
                 'pass <code>jsonp=False</code> to disable')
    def json(self, data={'result': 'turq'}, jsonp=True):
        """Set up a JSON or JSONP response.
        
        `data` will be serialized into an ``application/json`` entity body.
        But if the request has a ``callback`` query parameter,
        `data` will be wrapped into a JSONP callback
        and served as ``application/javascript``,
        unless you set `jsonp` to `False`.
        """
        self.ctype(lambda req: 'application/javascript'
                               if jsonp and 'callback' in req.query
                               else 'application/json')
        self.body(lambda req: (
            '%s(%s);' % (req.query['callback'], json.dumps(req.p(data)))
            if jsonp and 'callback' in req.query
            else json.dumps(req.p(data))
        ))
        return self
    
    @Cheat.entry('[code]', 'JavaScript')
    def js(self, code='alert("Turq");'):
        """Set up an ``application/javascript`` response."""
        return self.ctype('application/javascript').body(code)
    
    @Cheat.entry('[code]')
    def xml(self, code='<turq></turq>'):
        """Set up an ``application/xml`` response."""
        return self.ctype('application/xml').body(code)
    
    @Cheat.entry('location, [status=302]')
    def redirect(self, location, status=httplib.FOUND):
        """Set up a redirection response."""
        return self.status(status).header('Location', location)
    
    @Cheat.entry('name, value, [max_age], [path]...')
    def cookie(self, name, value, max_age=None, expires=None, path=None,
               secure=False, http_only=False):
        """Add a cookie `name` with `value`.
        
        The other arguments
        correspond to parameters of the ``Set-Cookie`` header.
        If specified, `max_age` and `expires` should be strings.
        Nothing is escaped.
        """
        def cookie_string(req):
            data = '%s=%s' % (req.p(name), req.p(value))
            if max_age is not None:
                data += '; Max-Age=%s' % req.p(max_age)
            if expires is not None:
                data += '; Expires=%s' % req.p(expires)
            if path is not None:
                data += '; Path=%s' % req.p(path)
            if secure:
                data += '; Secure'
            if http_only:
                data += '; HttpOnly'
            return data
        return self.add_header('Set-Cookie', cookie_string)
    
    @Cheat.entry('[realm]')
    def basic_auth(self, realm='Turq'):
        """Demand HTTP basic authentication (status code 401)."""
        self.status(httplib.UNAUTHORIZED)
        self.header('WWW-Authenticate',
                    lambda req: 'Basic realm="%s"' % req.p(realm))
        return self
    
    @Cheat.entry('[realm], [nonce]')
    def digest_auth(self, realm='Turq', nonce='twasbrillig'):
        """Demand HTTP digest authentication (status code 401)."""
        self.status(httplib.UNAUTHORIZED)
        self.header(
            'WWW-Authenticate',
            lambda req: 'Digest realm="%s", nonce="%s"' % (
                req.p(realm), req.p(nonce)
            )
        )
        return self
    
    @Cheat.entry('*methods', 'otherwise send 405 with a text error message')
    def allow(self, *methods):
        """Check the request method to be one of `methods` (case-insensitive).
        
        If it isn’t, send 405 Method Not Allowed
        with a plain-text error message.
        """
        self._allow = set(m.lower() for m in methods)
        return self
    
    @Cheat.entry()
    def cors(self):
        """Enable `CORS <http://www.w3.org/TR/cors/>`_ on the response.
        
        Currently this just sets ``Access-Control-Allow-Origin: *``.
        Preflight requests are not yet handled.
        """
        self._enable_cors = True
        return self.header('Access-Control-Allow-Origin', '*')
    
    @Cheat.entry('when', '“10 minutes” or “5 h” or “1 day”')
    def expires(self, when):
        """Set the expiration time of the response.
        
        `when` should be a specification
        of the number of minutes, hours or days,
        counted from the moment the rules are posted.
        Supported formats are: “10 min” or “10 minutes” or “5 h” or “5 hours”
        or “1 d” or “1 day”.
        """
        n, unit = when.split()
        n = int(n)
        dt = datetime.utcnow()
        if unit in ('minute', 'minutes', 'min'):
            dt += timedelta(seconds=(n * 60))
        elif unit in ('hour', 'hours', 'h'):
            dt += timedelta(seconds=(n * 3600))
        elif unit in ('day', 'days', 'd'):
            dt += timedelta(days=n)
        else:
            raise ValueError('unknown expires format: "%s"' % when)
        return self.header('Expires', dt.strftime('%a, %d %b %Y %H:%M:%S GMT'))
    
    @Cheat.entry()
    def gzip(self):
        """Apply ``Content-Encoding: gzip`` to the entity body.
        
        ``Accept-Encoding`` of the request is ignored.
        """
        self._gzip = True
        return self
    
    @Cheat.entry('', 'begin a sub-rule for the first hit...')
    def first(self):
        """Add a sub-rule that will be applied on a first request."""
        sub = Rule()
        self._chain = [sub]
        return sub
    
    @Cheat.entry('', '...the next hit...')
    def next(self):
        """Add a sub-rule that will be applied on a subsequent request."""
        assert self._chain, 'next() without first()'
        sub = Rule()
        self._chain.append(sub)
        return sub
    
    @Cheat.entry('', '...and all subsequent hits')
    def then(self):
        """Add a sub-rule that will be applied on all subsequent requests."""
        assert self._chain, 'then() without first()'
        self._final = Rule()
        return self._final
    
    @Cheat.entry('[probability]', 'start a stochastic sub-rule')
    def maybe(self, probability=0.1):
        """Add a sub-rule that will be applied with `probability`."""
        assert probability > 0
        sub = Rule()
        self._maybe.append((sub, probability))
        assert sum(p for s, p in self._maybe) <= 1
        return sub
    
    @Cheat.entry('', 'complement all <code>maybe</code>s')
    def otherwise(self):
        """Add a sub-rule that complements all :meth:`~Rule.maybe` rules.
        
        This is just a shortcut
        that adds a `maybe` sub-rule
        with a probability equal to 1 minus all currently defined `maybe`.
        Thus, it must come after all `maybe`.
        """
        return self.maybe(1 - sum(p for s, p in self._maybe))
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return False
    
    def apply_normal(self, req, resp):
        if self._delay is not None:
            time.sleep(req.p(self._delay))
        if self._status is not None:
            resp.status = req.p(self._status)
        if self._body is not None:
            resp.body = req.p(self._body)
    
    def apply_headers(self, req, resp):
        for op, name, value, params in self._headers:
            if op == 'set':
                resp.set_header(req.p(name), req.p(value), **params)
            elif op == 'add':
                resp.add_header(req.p(name), req.p(value), **params)
    
    def apply_chain(self, req, resp):
        if self._counter >= len(self._chain):
            if self._final is not None:
                self._final.apply(req, resp)
            else:
                self._counter = 0
        if self._counter < len(self._chain):
            self._chain[self._counter].apply(req, resp)
            self._counter += 1
    
    def apply_maybe(self, req, resp):
        x = random.random()
        pos = 0
        for sub, prob in self._maybe:
            pos += prob
            if x < pos:
                sub.apply(req, resp)
                return
    
    def apply_processor(self, req, resp):
        if self._processor is not None:
            sub = Rule()
            self._processor(req, sub)
            sub.apply(req, resp)
    
    def apply_allow(self, req, resp):
        if self._allow is not None:
            if req.method.lower() not in self._allow:
                resp.status = httplib.METHOD_NOT_ALLOWED
                resp.set_header('Content-Type', 'text/plain')
                resp.body = 'Method %s not allowed here' % req.method
    
    def apply_gzip(self, req, resp):
        if self._gzip and resp.body:
            zbuf = StringIO()
            zfile = gzip.GzipFile(fileobj=zbuf, mode='w')
            zfile.write(resp.body)
            zfile.close()
            resp.body = zbuf.getvalue()
            resp.set_header('Content-Encoding', 'gzip')
    
    def apply(self, req, resp):
        self.apply_normal(req, resp)
        self.apply_headers(req, resp)
        self.apply_chain(req, resp)
        self.apply_maybe(req, resp)
        self.apply_allow(req, resp)
        self.apply_gzip(req, resp)
        self.apply_processor(req, resp)


class PathRule(Rule):
    
    def __init__(self, path='*', trailing_slash=True):
        self.regex = re.compile(
            '^' + re.escape(path).replace('\\*', '.*') +
            ('/?' if trailing_slash else '') + '$')
        super(PathRule, self).__init__()
    
    def matches(self, req):
        return bool(self.regex.search(req.path))


def parse_rules(code):
    rules = []
    def path(*args, **kwargs):
        rule = PathRule(*args, **kwargs)
        rules.append(rule)
        return rule
    exec code in {'path': path}
    return rules


CONSOLE_TPL = string.Template('''
<!DOCTYPE html
    PUBLIC "-//W3C//DTD HTML 4.01//EN"
    "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <title>Turq</title>
        <script type="text/javascript">
            window.onload = function() {
                window.setTimeout(function() {
                    document.getElementById('okay').innerText = '';
                }, 2000);
                document.getElementById('codeEntry').focus();
            };
        </script>
        <style type="text/css">
            body { margin: 2em; font-family: sans-serif; }
            #error { color: #FF0000; }
            #okay { color: #0E7C00; }
            #codeEntry { width: 55%; }
            .example { font-weight: bold; }
            #cheat {
                float: right;
                margin-left: 3em;
                width: 40%;
                padding-bottom: 3em;
            }
            #cheat th {
                text-align: left;
                padding-right: 0.5em;
            }
            #cheat th .args { font-weight: normal; }
            #cheat td, th {
                border-top: solid 1px #D8D8D8;
                padding-top: 0.3em;
                padding-bottom: 0.3em;
            }
            #cheat table { border-collapse: collapse; }
        </style>
    </head>
    <body>
        <div id="cheat">
            <h2>Cheat sheet</h2>
            $cheat
        </div>
        <h1>Turq</h1>
        <pre id="error">$error</pre>
        <form action="/+turq/" method="post">
            <div>
                <pre><textarea id="codeEntry" name="code"
                    rows="25" cols="80">$code</textarea></pre>
            </div>
            <div>
                <input type="submit" value="Commit" accesskey="s">
                <span id="okay">$okay</span>
            </div>
        </form>
        <p>
            <a href="https://github.com/vfaronov/turq">Turq</a> $version ·
            <a href="https://turq.readthedocs.org/">docs</a>
        </p>
    </body>
</html>
''')


def render_console(code, okay='', error=''):
    return CONSOLE_TPL.substitute(code=code, okay=okay, error=error,
                                  cheat=Cheat.format(), version=__version__)


class TurqHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    code = ''
    rules = []
    
    @classmethod
    def install_code(cls, code):
        cls.code = code
        cls.rules = parse_rules(code)
    
    def __getattr__(self, attr):
        if attr.startswith('do_'):
            return lambda: self.do(attr[3:])
    
    @property
    def path_without_query(self):
        return self.path.split('?')[0]
    
    @property
    def query(self):
        parts = self.path.split('?')
        if len(parts) > 1:
            q = parts[1]
            try:
                q = urlparse.parse_qs(q)
            except Exception:
                q = urlparse.parse_qs('')       # so it's still iterable
        else:
            q = urlparse.parse_qs('')
        return dict((k, v[0]) for k, v in q.items())
    
    @property
    def body(self):
        if 'Content-Length' in self.headers:
            return self.rfile.read(int(self.headers['Content-Length']))
    
    def do(self, method):
        if self.path_without_query == '/+turq/':
            self.do_console(method)
        else:
            self.do_mock(method)
    
    def parse_form(self):
        return urlparse.parse_qs(self.body)
    
    def version_string(self):
        return 'Turq/%s' % __version__
    
    def do_console(self, method):
        okay = error = ''
        if method == 'POST':
            try:
                form = self.parse_form()
                code = form.get('code', [''])[0].replace('\r\n', '\n')
                self.install_code(code)
                sys.stderr.write('--- New rules posted and activated ---\n')
                okay = 'okay'
            except Exception:
                error = traceback.format_exc()
        
        self.send_response(httplib.OK)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(render_console(self.code, okay, error))
    
    def do_mock(self, method):
        req = Request(method, self.path_without_query, self.query,
                      self.headers, self.body)
        resp = Response()
        for rule in self.rules:
            if rule.matches(req):
                rule.apply(req, resp)
        
        # Server and Date headers need special casing
        if 'Server' in resp.headers:
            self.version_string = lambda *args: resp.headers['Server']
        if 'Date' in resp.headers:
            self.date_time_string = lambda *args: resp.headers['Date']
        
        self.send_response(resp.status)
        for name, value in resp.headers.items():
            if name.lower() not in ('server', 'date'):
                self.send_header(name, value)
        self.end_headers()
        if resp.body and (method != 'HEAD'):
            self.wfile.write(resp.body)


def main():
    parser = OptionParser(usage='usage: %prog [-p PORT]')
    parser.add_option('-p', '--port', dest='port', type='int',
                      default=DEFAULT_PORT,
                      help='listen on PORT', metavar='PORT')
    options, args = parser.parse_args()
    
    server = BaseHTTPServer.HTTPServer(('0.0.0.0', options.port), TurqHandler)
    sys.stderr.write('Listening on port %d\n' % server.server_port)
    sys.stderr.write('Try http://%s:%d/+turq/\n' %
                     (socket.getfqdn(), server.server_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()


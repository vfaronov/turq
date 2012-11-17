#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.1.0'

import BaseHTTPServer
import collections
from cStringIO import StringIO
from datetime import datetime, timedelta
import email.message
import gzip
import httplib
import json
from optparse import OptionParser
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

Request = collections.namedtuple(
    'Request', ('method', 'path', 'query', 'headers', 'body'))

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


def make_text(bytes):
    buf = StringIO()
    written = 0
    words = 'lorem ipsum dolor sit amet, consectetur adipisicing elit'.split()
    while written < bytes:
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
        self._enable_cors = False
        self._enable_jsonp = False
        self._allow = None
        self._gzip = False
    
    @Cheat.entry('code')
    def status(self, code):
        self._status = code
        return self
    
    @Cheat.entry('name, value, **params', 'params are appended as k=v pairs')
    def header(self, name, value, **params):
        self._headers.append(('set', name, value, params))
        return self
    
    @Cheat.entry('name, value, **params', 'added, not replaced')
    def add_header(self, name, value, **params):
        self._headers.append(('add', name, value, params))
        return self
    
    @Cheat.entry('data')
    def body(self, data):
        self._body = data
        return self
    
    @Cheat.entry('path')
    def body_file(self, path):
        return self.body(open(path).read())
    
    @Cheat.entry('url', 'data from <var>url</var> is cached until Turq exits')
    def body_url(self, url):
        if url not in Rule.url_cache:
            Rule.url_cache[url] = urllib2.urlopen(url).read()
        return self.body(Rule.url_cache[url])
    
    @Cheat.entry('seconds')
    def delay(self, seconds):
        self._delay = seconds
        return self
    
    def __call__(self, proc):
        self._processor = proc
        return proc
    
    @Cheat.entry('mime_type', 'content type')
    def ctype(self, value):
        return self.header('Content-Type', value)
    
    @Cheat.entry('[text]', 'plain text')
    def text(self, text='Hello world!'):
        return self.ctype('text/plain; charset=utf-8').body(text)
    
    @Cheat.entry('[bytes]', 'roughly <var>bytes</var> of plain text')
    def lots_of_text(self, bytes=20000):
        return self.text(make_text(bytes))
    
    @Cheat.entry('[title], [text]', 'basic HTML page')
    def html(self, title='Hello world!', text='This is Turq!'):
        body = '''<!DOCTYPE html>
<html>
    <head>
        <title>%s</title>
    </head>
    <body>
        <h1>%s</h1>
        <p>%s</p>
    </body>
</html>''' % (title, title, text)
        return self.ctype('text/html; charset=utf-8').body(body)
    
    @Cheat.entry('[bytes]', 'roughly <var>bytes</var> of HTML')
    def lots_of_html(self, bytes=20000, title='Hello world!'):
        return self.html(
            title=title,
            text=make_text(bytes - 100).replace('\n\n', '</p><p>')
        )
    
    @Cheat.entry('[data]',
                 'JSONP is handled automatically, '
                 'pass <code>jsonp=False</code> to disable')
    def json(self, data={'result': 'turq'}, jsonp=True):
        self._enable_jsonp = jsonp
        return self.ctype('application/json').body(json.dumps(data))
    
    @Cheat.entry('[code]', 'JavaScript')
    def js(self, code='alert("Turq");'):
        return self.ctype('application/javascript')
    
    @Cheat.entry('[code]')
    def xml(self, code='<turq></turq>'):
        return self.ctype('application/xml').body(code)
    
    @Cheat.entry('location, [status=302]')
    def redirect(self, location, status=httplib.FOUND):
        return self.status(status).header('Location', location)
    
    @Cheat.entry('name, value, [max_age], [path]...')
    def cookie(self, name, value, max_age=None, expires=None, path=None,
               secure=False, http_only=False):
        data = '%s=%s' % (name, value)
        if max_age is not None:
            data += '; Max-Age=%s' % max_age
        if expires is not None:
            data += '; Expires=%s' % expires
        if path is not None:
            data += '; Path=%s' % path
        if secure:
            data += '; Secure'
        if http_only:
            data += '; HttpOnly'
        return self.add_header('Set-Cookie', data) 
    
    @Cheat.entry('[realm]')
    def basic_auth(self, realm='Turq'):
        return self.status(httplib.UNAUTHORIZED). \
                    header('WWW-Authenticate', 'Basic realm="%s"' % realm)
    
    @Cheat.entry('[realm], [nonce]')
    def digest_auth(self, realm='Turq', nonce='twasbrillig'):
        return self.status(httplib.UNAUTHORIZED). \
                    header('WWW-Authenticate',
                           'Digest realm="%s", nonce="%s"' % (realm, nonce))
    
    @Cheat.entry('*methods', 'otherwise send 405 with a text error message')
    def allow(self, *methods):
        self._allow = set(m.lower() for m in methods)
        return self
    
    @Cheat.entry()
    def cors(self):
        self._enable_cors = True
        return self.header('Access-Control-Allow-Origin', '*')
    
    @Cheat.entry('when', '“10 minutes” or “5 h” or “1 day”')
    def expires(self, when):
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
        self._gzip = True
        return self
    
    def first(self):
        sub = Rule()
        self._chain = [sub]
        return sub
    
    def next(self):
        assert self._chain, 'next() without first()'
        sub = Rule()
        self._chain.append(sub)
        return sub
    
    def then(self):
        assert self._chain, 'then() without first()'
        self._final = Rule()
        return self._final
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return False
    
    def _set_header(self, resp, name, value):
        del resp[name]
        resp[name] = value
    
    def apply_normal(self, req, resp):
        if self._delay:
            time.sleep(self._delay)
        if self._status is not None:
            resp.status = self._status
        if self._body is not None:
            resp.body = self._body
    
    def apply_headers(self, req, resp):
        for op, name, value, params in self._headers:
            if op == 'set':
                resp.set_header(name, value, **params)
            elif op == 'add':
                resp.add_header(name, value, **params)
    
    def apply_jsonp(self, req, resp):
        if self._enable_jsonp and ('callback' in req.query):
            resp.body = '%s(%s);' % (req.query['callback'][0], resp.body)
            resp.set_header('Content-Type', 'application/javascript')
    
    def apply_chain(self, req, resp):
        if self._counter >= len(self._chain):
            if self._final is not None:
                self._final.apply(req, resp)
            else:
                self._counter = 0
        if self._counter < len(self._chain):
            self._chain[self._counter].apply(req, resp)
            self._counter += 1
    
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
        self.apply_jsonp(req, resp)
        self.apply_chain(req, resp)
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
                vertical-align: top;
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
                <span id="okay" style="color: #0E7C00">$okay</span>
            </div>
        </form>
    </body>
</html>
''')


def render_console(code, okay='', error=''):
    return CONSOLE_TPL.substitute({
        'code': code,
        'okay': okay,
        'error': error,
        'cheat': Cheat.format()
    })


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
            return q
        else:
            return urlparse.parse_qs('')
    
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


if __name__ == '__main__':
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


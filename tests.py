# -*- coding: utf-8 -*-

from cStringIO import StringIO
from datetime import datetime, timedelta
import gzip
import httplib
import socket
import subprocess
import time
import unittest
import urllib

socket.setdefaulttimeout(5)


class TurqTestCase(unittest.TestCase):
    
    def setUp(self):
        self.proc = subprocess.Popen(
            # exec prevents the shell from spawning a subprocess
            # which then fails to terminate.
            # http://stackoverflow.com/questions/4789837/
            'exec python turq.py', shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)
    
    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)
    
    def request(self, method, path, headers=None, body=None):
        conn = httplib.HTTPConnection('127.0.0.1', 13085)
        conn.request(method, path, body, headers or {})
        resp = conn.getresponse()
        return resp, resp.read()
    
    def install(self, code, check=True):
        info, data = self.request(
            'POST', '/+turq/',
            {'Content-Type': 'application/x-www-form-urlencoded'},
            urllib.urlencode({'code': code})
        )
        self.assertEqual(info.status, httplib.OK)
        if check:
            self.assert_('>okay<' in data)
        return info, data
    
    def test_status(self):
        self.install("path().status(403)")
        info, data = self.request('GET', '/')
        self.assertEqual(info.status, 403)
    
    def test_header(self):
        self.install("path().header('X-Foo', 'bar', baz=None)")
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg['X-Foo'], 'bar; baz')
    
    def test_add_header(self):
        self.install("path().add_header('X-Foo', 'bar'). \\\n"
                     "       add_header('X-Foo', 'baz', qux='yes')")
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg.getheaders('X-Foo'),
                         ['bar', 'baz; qux="yes"'])
    
    def test_overwrite_header(self):
        self.install("path().add_header('X-Foo', 'bar'). \\\n"
                     "       add_header('X-Foo', 'baz'). \\\n"
                     "       add_header('X-Quux', 'yes')\n"
                     "path('/sub').header('X-Foo', 'xyzzy')")
        info, data = self.request('GET', '/sub')
        self.assertEqual(info.msg['X-Foo'], 'xyzzy')
        self.assertEqual(info.msg['X-Quux'], 'yes')
    
    def test_body(self):
        self.install("path().body('hello world')")
        info, data = self.request('GET', '/')
        self.assertEqual(data, 'hello world')
    
    def test_paths(self):
        self.install("path().header('X-Foo', 'bar')\n"
                     "path('/one/*').text('part one')\n"
                     "path('*.two').text('part two')\n")
        
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assert_(not data)
        
        info, data = self.request('GET', '/one')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assert_(not data)
        
        info, data = self.request('GET', '/one/')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assertEqual(data, 'part one')
        
        info, data = self.request('GET', '/one/sub/')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assertEqual(data, 'part one')
        
        info, data = self.request('GET', '/index.two')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assertEqual(data, 'part two')
        
        info, data = self.request('GET', '/one/index.two?id=495')
        self.assertEqual(info.msg['X-Foo'], 'bar')
        self.assertEqual(data, 'part two')
    
    def test_allow_trailing_slash(self):
        self.install("path('/foo').text('yep')")
        info, data = self.request('GET', '/foo/')
        self.assertEqual(data, 'yep')
    
    def test_forbid_trailing_slash(self):
        self.install("path('/foo', trailing_slash=False).text('yep')")
        info, data = self.request('GET', '/foo/')
        self.assert_(not data)
    
    def test_delay(self):
        self.install("path().delay(3).text('yep')")
        dt1 = datetime.now()
        info, data = self.request('GET', '/')
        dt2 = datetime.now()
        self.assert_(dt2 - dt1 >= timedelta(seconds=3))
        self.assertEqual(data, 'yep')
    
    def test_processor(self):
        self.install("@path()\n"
                     "def process(req, r):\n"
                     "    body = 'Hey %s! You did a %s on %s!' % (\n"
                     "        req.headers['User-Agent'],\n"
                     "        req.method, req.path)\n"
                     "    if 'id' in req.query:\n"
                     "        body += ' You requested item %s!' % (\n"
                     "            req.query['id'])\n"
                     "    if req.body:\n"
                     "        body += ' %d bytes!' % len(req.body)\n"
                     "    r.text(body)\n")
        
        info, data = self.request('GET', '/foo/?id=67&bar=yes',
                                  {'User-agent': 'test suite'})
        self.assertEqual(data,
                         'Hey test suite! You did a GET on /foo/! '
                         'You requested item 67!')
        
        info, data = self.request('POST', '/bar/baz',
                                  {'User-Agent': 'test suite'},
                                  'quux=xyzzy')
        self.assertEqual(data,
                         'Hey test suite! You did a POST on /bar/baz! '
                         '10 bytes!')
    
    def test_cycle(self):
        self.install("with path() as r:\n"
                     "    r.first().text('one')\n"
                     "    r.next().text('two')\n"
                     "    r.next().text('three')\n")
        results = []
        for i in range(5):
            info, data = self.request('GET', '/')
            results.append(data)
        self.assertEqual(results, ['one', 'two', 'three', 'one', 'two'])
    
    def test_achieve_and_hold(self):
        self.install("with path() as r:\n"
                     "    r.first().text('one')\n"
                     "    r.next().text('two')\n"
                     "    r.then().text('three')\n")
        results = []
        for i in range(5):
            info, data = self.request('GET', '/')
            results.append(data)
        self.assertEqual(results, ['one', 'two', 'three', 'three', 'three'])
    
    def test_syntax_error(self):
        info, data = self.install("path('*).text()", check=False)
        self.assert_('SyntaxError' in data)
    
    def test_server_and_date(self):
        self.install("path().header('SERVER', 'Test-RuleSet/0.1'). \\\n"
                     "       header('DATE', 'Sat, 17 Nov 2012 00:00:00 GMT')")
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg['Server'], 'Test-RuleSet/0.1')
        self.assertEqual(info.msg['Date'], 'Sat, 17 Nov 2012 00:00:00 GMT')
    
    def test_jsonp(self):
        self.install("path().json()")
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg['Content-Type'], 'application/json')
        info, data = self.request('GET', '/?callback=callback')
        self.assertEqual(info.msg['Content-Type'], 'application/javascript')
        self.assert_('callback(' in data)
    
    def test_forbid_jsonp(self):
        self.install("path().json(jsonp=False)")
        info, data = self.request('GET', '/?callback=callback')
        self.assertEqual(info.msg['Content-Type'], 'application/json')
    
    def test_body_from_file(self):
        self.install("path().body_file('README.rst')")
        info, data = self.request('GET', '/')
        self.assert_('Usage' in data)
    
    def test_body_from_url(self):
        self.install("path().body_url('http://httpbin.org/html')")
        info, data = self.request('GET', '/')
        self.assert_('Herman Melville - Moby-Dick' in data)
    
    def test_cookies(self):
        self.install(
            "path().cookie('sessionid', '123', max_age=3600). \\\n"
            "       cookie('evil_tracking', 'we_own_you', http_only=True)"
        )
        info, data = self.request('GET', '/')
        self.assertEqual(
            info.msg.getheaders('Set-Cookie'),
            ['sessionid=123; Max-Age=3600',
             'evil_tracking=we_own_you; HttpOnly']
        )
    
    def test_allow(self):
        self.install("path().allow('GET', 'HEAD').text('fine!')")
        info, data = self.request('GET', '/')
        self.assertEqual(data, 'fine!')
        info, data = self.request('DELETE', '/')
        self.assertEqual(info.status, httplib.METHOD_NOT_ALLOWED)
    
    def test_gzip(self):
        self.install("path().text('compress this!').gzip()")
        info, data = self.request('GET', '/')
        self.assertEqual(gzip.GzipFile(fileobj=StringIO(data)).read(),
                         'compress this!')
        self.assertEqual(info.msg['Content-Encoding'], 'gzip')
    
    def test_lots_of_text(self):
        self.install("path().lots_of_text(30000)")
        info, data = self.request('GET', '/')
        self.assert_(data.count('\n') > 10)
        self.assert_(abs(len(data) - 30000) <= 100)
    
    def test_lots_of_html(self):
        self.install("path().lots_of_html(30000)")
        info, data = self.request('GET', '/')
        self.assert_(data.count('<p') > 10)
        self.assert_(abs(len(data) - 30000) <= 300)
    
    def test_maybe(self):
        self.install("with path() as r:\n"
                     "    r.maybe(0.3).text('foo')\n"
                     "    r.maybe(0.1).text('bar')\n"
                     "    r.otherwise().text('baz')\n")
        foo_count = baz_count = 0
        for i in xrange(100):
            info, data = self.request('GET', '/')
            self.assert_(data in ('foo', 'bar', 'baz'))
            if data == 'foo':
                foo_count += 1
            elif data == 'baz':
                baz_count += 1
        self.assert_(20 <= foo_count <= 40)
        self.assert_(50 <= baz_count <= 70)
    
    def test_lambda_status(self):
        self.install("with path() as r:\n"
                     "    r.status(lambda req: int(req.query['st']))\n")
        info, data = self.request('GET', '/?st=404')
        self.assertEqual(info.status, 404)
        info, data = self.request('GET', '/?st=501')
        self.assertEqual(info.status, 501)
    
    def test_lambda_header(self):
        self.install("with path() as r:\n"
                     "    r.header('Server',\n"
                     "             lambda req: 'Foo/' + req.query['ver'])")
        info, data = self.request('GET', '/?ver=0.4.6')
        self.assertEqual(info.msg['Server'], 'Foo/0.4.6')
    
    def test_lambda_body(self):
        self.install("with path() as r:\n"
                     "    r.body(lambda req: 'Hello ' + req.query['name'])")
        info, data = self.request('GET', '/?name=world')
        self.assertEqual(data, 'Hello world')
    
    def test_lambda_json(self):
        self.install("with path() as r:\n"
                     "    r.json(lambda req: {'id': req.query['id']})")
        info, data = self.request('GET', '/?id=foo')
        self.assertEqual(data, '{"id": "foo"}')
    
    def test_lambda_html(self):
        self.install("with path() as r:\n"
                     "    r.html(title=lambda req: req.query['q'])")
        info, data = self.request('GET', '/?q=bar')
        self.assert_('<title>bar</title>' in data)
    
    def test_lambda_cookie(self):
        self.install("with path() as r:\n"
                     "    r.cookie('foo', 'bar', path=lambda req: req.path)")
        info, data = self.request('GET', '/quux/')
        self.assertEqual(info.msg['Set-Cookie'], 'foo=bar; Path=/quux/')
    
    def test_lambda_auth(self):
        self.install("with path() as r:\n"
                     "    r.basic_auth(realm=lambda req: req.query['r'])")
        info, data = self.request('GET', '/?r=somewhere')
        self.assertEqual(info.msg['WWW-Authenticate'],
                         'Basic realm="somewhere"')


if __name__ == '__main__':
    unittest.main()


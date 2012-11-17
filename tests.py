# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import httplib
import socket
import subprocess
import time
import unittest
import urllib

PORT = 31092
socket.setdefaulttimeout(5)


class TurqTestCase(unittest.TestCase):
    
    def setUp(self):
        self.proc = subprocess.Popen(
            # exec prevents the shell from spawning a subprocess
            # which then fails to terminate.
            # http://stackoverflow.com/questions/4789837/
            'exec python turq.py -p %d' % PORT, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.port = PORT
        time.sleep(0.2)
    
    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)
    
    def request(self, method, path, headers=None, body=None):
        conn = httplib.HTTPConnection('127.0.0.1', self.port)
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
        self.install("path('*').status(403)")
        info, data = self.request('GET', '/')
        self.assertEqual(info.status, 403)
    
    def test_header(self):
        self.install("path('*').header('X-Foo', 'bar; baz')")
        info, data = self.request('GET', '/')
        self.assertEqual(info.msg['X-Foo'], 'bar; baz')
    
    def test_body(self):
        self.install("path('*').body('hello world')")
        info, data = self.request('GET', '/')
        self.assertEqual(data, 'hello world')
    
    def test_paths(self):
        self.install("path('*').header('X-Foo', 'bar')\n"
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
    
    def test_delay(self):
        self.install("path('*').delay(3).text('yep')")
        dt1 = datetime.now()
        info, data = self.request('GET', '/')
        dt2 = datetime.now()
        self.assert_(dt2 - dt1 >= timedelta(seconds=3))
        self.assertEqual(data, 'yep')
    
    def test_processor(self):
        self.install("@path('*')\n"
                     "def process(req, r):\n"
                     "    body = 'Hey %s! You did a %s on %s!' % (\n"
                     "        req.headers['User-Agent'],\n"
                     "        req.method, req.path)\n"
                     "    if 'id' in req.query:\n"
                     "        body += ' You requested item %s!' % (\n"
                     "            req.query['id'][0])\n"
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
        self.install("with path('*') as r:\n"
                     "    r.first().text('one')\n"
                     "    r.next().text('two')\n"
                     "    r.next().text('three')\n")
        results = []
        for i in range(5):
            info, data = self.request('GET', '/')
            results.append(data)
        self.assertEqual(results, ['one', 'two', 'three', 'one', 'two'])
    
    def test_achieve_and_hold(self):
        self.install("with path('*') as r:\n"
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


if __name__ == '__main__':
    unittest.main()


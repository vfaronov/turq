# -*- coding: utf-8 -*-

import distutils.core
import ast
import re

def find_version(path):
    _version_re = re.compile(r'__version__\s+=\s+(.*)')
    with open(path, 'rb') as f:
        return str(ast.literal_eval(_version_re.search(
            f.read().decode('utf-8')).group(1)))

distutils.core.setup(
    name='turq',
    version=find_version('turq.py'),
    description='Mock HTTP server',
    long_description=open('README.rst').read(),
    author='Vasiliy Faronov',
    author_email='vfaronov@gmail.com',
    url='https://github.com/vfaronov/turq',
    py_modules=['turq']
)


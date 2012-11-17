# -*- coding: utf-8 -*-

import distutils.core

import turq

distutils.core.setup(
    name='turq',
    version=turq.__version__,
    description='Mock HTTP server',
    long_description=open('README.rst').read(),
    author='Vasiliy Faronov',
    author_email='vfaronov@gmail.com',
    url='https://github.com/vfaronov/turq',
    py_modules=['turq']
)


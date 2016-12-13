#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/11
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import os, sys, setuptools
from setuptools import setup, find_packages

# require python 2.7+
if sys.hexversion < 0x02070000:
  raise RuntimeError('This package requires python 2.7 or better')

heredir = os.path.abspath(os.path.dirname(__file__))
def read(*parts, **kw):
  try:    return open(os.path.join(heredir, *parts)).read()
  except: return kw.get('default', '')

test_dependencies = [
  'nose                 >= 1.3.0',
  'coverage             >= 3.5.3',
  'WebTest              >= 1.4.0',
  'SQLAlchemy           >= 0.8.2',
]

dependencies = [
  'pyramid              >= 1.4.2',
  'APScheduler          >= 2.1.0',
  'kombu                >= 2.5.10',
  'transaction          >= 1.4.1',
  'six                  >= 1.6.1',
]

entrypoints = {
  'console_scripts': [
    'pscheduler         = pyramid_scheduler.pscheduler:main',
  ],
}

classifiers = [
  'Development Status :: 5 - Production/Stable',
  'Intended Audience :: Developers',
  'Programming Language :: Python',
  'Framework :: Pyramid',
  'Environment :: Console',
  'Environment :: Web Environment',
  'Operating System :: OS Independent',
  'Topic :: Internet',
  'Topic :: Software Development',
  'Topic :: Internet :: WWW/HTTP',
  'Topic :: Internet :: WWW/HTTP :: WSGI',
  'Topic :: Software Development :: Libraries :: Application Frameworks',
  'Natural Language :: English',
  'License :: OSI Approved :: MIT License',
  'License :: Public Domain',
]

setup(
  name                  = 'pyramid_scheduler',
  version               = read('VERSION.txt', default='0.0.1').strip(),
  description           = 'A pyramid plugin that allows asynchronous and deferred task scheduling and management.',
  long_description      = read('README.rst'),
  classifiers           = classifiers,
  author                = 'Philip J Grabner, Cadit Health Inc',
  author_email          = 'oss@cadit.com',
  url                   = 'http://github.com/cadithealth/pyramid_scheduler',
  keywords              = 'web wsgi pyramid asynchronous task scheduling management scheduler',
  packages              = setuptools.find_packages(),
  include_package_data  = True,
  zip_safe              = True,
  install_requires      = dependencies,
  tests_require         = test_dependencies,
  test_suite            = 'pyramid_scheduler',
  entry_points          = entrypoints,
  license               = 'MIT (http://opensource.org/licenses/MIT)',
)

#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

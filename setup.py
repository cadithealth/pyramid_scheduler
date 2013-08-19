#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/11
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import os, sys, setuptools
from setuptools import setup

# require python 2.7+
assert(sys.version_info[0] > 2
       or sys.version_info[0] == 2
       and sys.version_info[1] >= 7)

here = os.path.abspath(os.path.dirname(__file__))
def read(*parts):
  try:    return open(os.path.join(here, *parts)).read()
  except: return ''

test_requires = [
  'nose                 >= 1.2.1',
  'coverage             >= 3.5.3',
  ]

requires = [
  'pyramid              >= 1.4',
  'distribute           >= 0.6.24',
  ]

setup(
  name                  = 'pyramid_scheduler',
  version               = '0.2.3',
  description           = 'A pyramid plugin that allows asynchronous and deferred task scheduling and management.',
  long_description      = read('README.rst'),
  classifiers           = [
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
    ],
  author                = 'Philip J Grabner, Cadit Health Inc',
  author_email          = 'oss@cadit.com',
  url                   = 'http://github.com/cadithealth/pyramid_scheduler',
  keywords              = 'web wsgi pyramid asynchronous task scheduling management scheduler',
  packages              = setuptools.find_packages(),
  include_package_data  = True,
  zip_safe              = True,
  install_requires      = requires,
  tests_require         = test_requires,
  test_suite            = 'pyramid_scheduler',
  entry_points          = {
    'console_scripts': [
      'pscheduler = pyramid_scheduler.pscheduler:main',
    ],
  },
  license               = 'MIT (http://opensource.org/licenses/MIT)',
  )

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------

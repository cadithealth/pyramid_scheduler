#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/11
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import os, sys, re
from setuptools import setup, find_packages

# require python 2.7+
assert(sys.version_info[0] > 2
       or sys.version_info[0] == 2
       and sys.version_info[1] >= 7)

here = os.path.abspath(os.path.dirname(__file__))
try:
  README = open(os.path.join(here, 'README.txt')).read()
except IOError:
  README = ''

#------------------------------------------------------------------------------
# ugh. why couldn't github just have supported rst??? ignats.
#------------------------------------------------------------------------------
mdheader = re.compile('^(#+) (.*)$', flags=re.MULTILINE)
mdlevels = '=-~+"\''
def hdrepl(match):
  lvl = len(match.group(1)) - 1
  if lvl < 0:
    lvl = 0
  if lvl >= len(mdlevels):
    lvl = len(mdlevels) - 1
  ret = match.group(2).strip()
  return ret + '\n' + ( mdlevels[lvl] * len(ret) ) + '\n'
#------------------------------------------------------------------------------
mdquote = re.compile('^```( python)?\n(.*?)\n```\n', flags=re.MULTILINE|re.DOTALL)
def qtrepl(match):
  if match.group(1) == ' python':
    ret = '.. code-block:: python\n'
  else:
    ret = '::\n'
  for line in match.group(2).split('\n'):
    if len(line.strip()) <= 0:
      ret += '\n'
    else:
      ret += '\n  ' + line
  return ret + '\n'
#------------------------------------------------------------------------------
def md2rst(text):
  text = mdquote.sub(qtrepl, text)
  text = mdheader.sub(hdrepl, text)
  return text
#------------------------------------------------------------------------------
README = md2rst(README)

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
  version               = '0.2.2',
  description           = 'A pyramid plugin that allows asynchronous and deferred task scheduling and management.',
  long_description      = README,
  classifiers           = [
    'Development Status :: 4 - Beta',
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
  packages              = find_packages(),
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

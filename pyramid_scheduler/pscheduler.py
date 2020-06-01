# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler.pscheduler
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
Launches the ``pscheduler`` background process that is responsible for
actually executing the asynchronous and/or deferred tasks in
non-combined mode.
'''

import os
import sys
import subprocess
import time
import argparse
import logging
import threading
import transaction

from pyramid.scripts.pserve import install_reloader, _turn_sigterm_into_systemexit
from pyramid.paster import setup_logging, get_app

#------------------------------------------------------------------------------

log = None # logging.getLogger(__name__)

RELOADERENV = 'PSCHEDULER_RUN_RELOADER'

#------------------------------------------------------------------------------
def restart_with_reloader(options):
  log.info('starting subprocess with file monitor')
  while True:
    args = [sys.executable] + sys.argv
    new_environ = os.environ.copy()
    new_environ[RELOADERENV] = 'true'
    proc = None
    try:
      try:
        _turn_sigterm_into_systemexit()
        proc = subprocess.Popen(args, env=new_environ)
        log.info('subprocess started (PID %d)', proc.pid)
        exit_code = proc.wait()
        proc = None
      except KeyboardInterrupt:
        log.info('^C caught in monitor process')
        return 1
    finally:
      if proc is not None:
        try:
          import signal
          os.kill(proc.pid, signal.SIGTERM)
        except (ImportError, OSError, IOError):
          pass
    if exit_code == 3:
      # why 3? no idea. copied from pserve...
      log.info('restarting due to file change (exit code: %d)', exit_code)
      continue
    if not options.restart:
      return exit_code
    log.info('restarting in %d seconds (unexpected exit code: %d)',
             options.restart_interval, exit_code)
    time.sleep(options.restart_interval)
    log.info('restarting now')


#------------------------------------------------------------------------------
def main():

  parser = argparse.ArgumentParser(
    description=
    'Launch the pyramid-scheduler job execution process.'
    ' This process is only required for pyramid-scheduler'
    ' configurations that are not running in "combined" mode'
    ' (i.e. all-in-one-process).'
    )

  parser.add_argument(
    '--app-name', metavar='NAME',
    dest='appName', default='main',
    help='Load the named application (default: %(default)s)')

  parser.add_argument(
    '-q', '--queue', metavar='NAME',
    dest='queues', action='append', default=[],
    help='Restrict queues that this scheduler will handle - if not'
         ' specified, all queues will be handled (can be specified'
         ' multiple times)')

  parser.add_argument(
    '--reload',
    action='store_true',
    help='Use auto-restart file monitor')

  parser.add_argument(
    '--reload-interval', metavar='SECONDS',
    dest='reload_interval', default=1, type=int,
    help='Seconds between checking files (default: %(default)i)')

  parser.add_argument(
    '--restart',
    action='store_true',
    help='Automatically restart on unexpected exit')

  parser.add_argument(
    '--restart-interval', metavar='SECONDS',
    dest='restart_interval', default=5, type=int,
    help='Seconds to wait after an unexpected exit'
         ' (default: %(default)i)')

  parser.add_argument(
    '--message', metavar='TEXT',
    help='Message to send to the current consumer (no check is'
         ' made to ensure that it is currently running)')

  parser.add_argument(
    'configUri', metavar='CONFIG-URI',
    help='The configuration URI or filename')

  options = parser.parse_args()

  setup_logging(options.configUri)
  global log
  log = logging.getLogger(__name__)

  if options.reload:
    if os.environ.get(RELOADERENV) == 'true':
      log.info('installing reloading file monitor')
      # todo: the problem with pserve's implementation of the
      #       restarter is that it uses `os._exit()` which is
      #       a "rude" exit and does not allow APS's atexit()
      #       registrations to kick in... use a better
      #       implementation!
      install_reloader(options.reload_interval, [options.configUri])
    else:
      return restart_with_reloader(options)

  try:
    log.debug('loading application from "%s"', options.configUri)
    from pyramid_scheduler.scheduler import Scheduler
    app = get_app(options.configUri, name=options.appName)
    if not hasattr(app.registry, 'scheduler'):
      log.error('application did not load a scheduler (try'
                ' "config.include(\'pyramid_scheduler\')") - aborting')
      return 10
    if options.message:
      with transaction.manager:
        app.registry.scheduler.broker.send(options.message)
      return 0
    if app.registry.scheduler.conf.combined:
      log.error('application is configured for combined (i.e. single-process) operation - aborting')
      return 11
    log.debug('starting consumer process on queues %r', options.queues)
    app.registry.scheduler.startConsumer(daemon=True, queues=options.queues)
    register_for_graceful_shutdown(app)
    wait_for_exit()
  except (KeyboardInterrupt, SystemExit):
    return 0
  except Exception:
    log.exception('error while starting pscheduler')
    return 20

#------------------------------------------------------------------------------
def wait_for_exit():
  # can't use conditions (which would be cleaner), because they are not
  # interruptible (http://bugs.python.org/issue8844)
  while True:
    try:
      time.sleep(86400)
    except (KeyboardInterrupt, SystemExit):
      return

#------------------------------------------------------------------------------
def register_for_graceful_shutdown(app):
  # catch SIGTERM signals and exit gracefully
  try:
    import signal
  except ImportError:
    log.warning('SIGTERM signal handler could not be installed - graceful shutdown disabled')
    return
  def gracefulShutdown(signo=None, frame=None):
    log.info('shutting down pscheduler')
    # sys.exit will cause APS's "atexit" handler to be called
    app.registry.scheduler.shutdown()
    sys.exit(0)
  signal.signal(signal.SIGTERM, gracefulShutdown)

#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

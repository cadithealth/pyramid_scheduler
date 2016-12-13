# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
The ``pyramid-scheduler`` pyramid plugin allows asynchronous and
deferred task scheduling and management.
'''

import sys
from . import api
from .scheduler import Scheduler

#------------------------------------------------------------------------------
def includeme(config):
  config.registry.scheduler = Scheduler(
    settings = config.registry.settings,
    appreg   = config.registry,
    )
  config.registry.scheduler.startProducer()
  # todo: there *must* be a better way of determining whether or not i am
  #       in an env where i should start the consumer...
  if config.registry.scheduler.conf.combined \
      and not [e for e in sys.argv if e.endswith('pshell') or e.endswith('pscheduler')]:
    config.registry.scheduler.startConsumer()

#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

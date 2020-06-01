# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler.engine
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import sys, time, pickle
from .util import adict

#------------------------------------------------------------------------------
class InvalidJob(Exception): pass
class InvalidQueue(Exception): pass
class InvalidMessage(Exception): pass

#------------------------------------------------------------------------------
class Event(adict):

  MESSAGE       = 'message'
  JOB_CREATED   = 'job.created'
  JOB_EXECUTED  = 'job.executed'
  JOB_CANCELED  = 'job.canceled'
  JOB_REMOVED   = 'job.removed'

  #----------------------------------------------------------------------------
  def __init__(self, type, **params):
    self.type = type
    self.update(params)

  #----------------------------------------------------------------------------
  def __repr__(self):
    return '<%s.Event %s=%r>' \
      % (__name__, self.type,
         {k: v for k, v in self.items() if k != 'type'})


#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

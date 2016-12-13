# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler.util
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

import time, datetime, re, uuid
import apscheduler.events

#------------------------------------------------------------------------------
class InvalidDuration(Exception): pass

#------------------------------------------------------------------------------
class adict(dict):
  def __getattr__(self, key):
    if key.startswith('__') and key.endswith('__'):
      # note: allows an adict to be pickled with protocols 0, 1, and 2
      #       which treat the following specially:
      #         __getstate__, __setstate__, __slots__, __getnewargs__
      return dict.__getattr__(self, key)
    return self.get(key, None)
  def __setattr__(self, key, value):
    self[key] = value
    return self
  def __delattr__(self, key):
    if key in self:
      del self[key]
    return self
  def update(self, *args, **kw):
    args = [e for e in args if e]
    dict.update(self, *args, **kw)
    return self
  @staticmethod
  def __dict2adict__(subject, recursive=False):
    if isinstance(subject, list):
      if not recursive:
        return subject
      return [adict.__dict2adict__(val, True) for val in subject]
    if not isinstance(subject, dict):
      return subject
    ret = adict(subject)
    if not recursive:
      return ret
    for key, val in ret.items():
      ret[key] = adict.__dict2adict__(val, True)
    return ret

#------------------------------------------------------------------------------
durRE   = re.compile(r'\s*(\d+|\d*\.\d+)\s*([wdhms])\s*')
durMult = dict(w=604800, d=86400, h=3600, m=60, s=1)
def asdur(spec):
  ret = 0
  curspec = spec
  while True:
    match = durRE.match(curspec)
    if not match:
      raise InvalidDuration(spec)
    ret += float(match.group(1)) * durMult[match.group(2)]
    curspec = spec[match.end():]
    if len(curspec) <= 0:
      break
  return ret

#------------------------------------------------------------------------------
def addPrefix(src, prefix):
  return adict({prefix + k: v for k, v in src.items()})

#------------------------------------------------------------------------------
def makeID():
  return str(uuid.uuid4())

#------------------------------------------------------------------------------
def apsEventCode2String(code):
  for key in dir(apscheduler.events):
    if code is getattr(apscheduler.events, key):
      return key
  return None

#------------------------------------------------------------------------------
def apsevents_repr(self):
  if isinstance(self, apscheduler.events.JobStoreEvent):
    if not hasattr(self, 'job'):
      return '<apscheduler.events.JobStoreEvent code=%s, store=%s>' \
        % (apsEventCode2String(self.code), self.alias)
    return '<apscheduler.events.JobStoreEvent code=%s, store=%s, job=%r>' \
      % (apsEventCode2String(self.code), self.alias, self.job)
  if isinstance(self, apscheduler.events.JobEvent):
    return '<apscheduler.events.JobEvent code=%s, job=%r>' \
      % (apsEventCode2String(self.code), self.job)
  return '<apscheduler.events.SchedulerEvent code=%s>' \
    % (apsEventCode2String(self.code),)
apscheduler.events.SchedulerEvent.__repr__ = apsevents_repr

#------------------------------------------------------------------------------
def cull(**kw):
  return {key : value for key, value in kw.items() if value is not None}

#------------------------------------------------------------------------------
def resolve(spec):
  if not spec or callable(spec):
    return spec
  if ':' in spec:
    spec, attr = spec.split(':', 1)
    return getattr(resolve(spec), attr)
  spec = spec.split('.')
  used = spec.pop(0)
  found = __import__(used)
  for cur in spec:
    used += '.' + cur
    try:
      found = getattr(found, cur)
    except AttributeError:
      __import__(used)
      found = getattr(found, cur)
  return found

#------------------------------------------------------------------------------
def now():
  return time.time()

#------------------------------------------------------------------------------
def ts2dt(ts):
  # NOTE: APS requires naive datetimes... ugh. so need to return a
  # naive datetime in local timezone.
  return datetime.datetime.fromtimestamp(ts)

#------------------------------------------------------------------------------
def dt2ts(dt):
  # NOTE: APS requires naive datetimes... ugh. so need to ignore the
  # fact that the datetime is naive.
  return float(time.mktime(dt.timetuple()))

#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler.scheduler
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
The pyramid-scheduler scheduling service.
'''

import time
import datetime
import logging
import threading
from contextlib import contextmanager

import transaction
import apscheduler
import apscheduler.scheduler
import apscheduler.events
from pyramid.settings import asbool, aslist
from apscheduler.jobstores.ram_store import RAMJobStore
from apscheduler.util import combine_opts, ref_to_obj, obj_to_ref

from .util import adict, asdur, addPrefix, makeID, cull, now, ts2dt, dt2ts, resolve
from . import api, broker

log = logging.getLogger(__name__)

#------------------------------------------------------------------------------
def pyramid_scheduler_wrapper(schedulerID, jobID, task):
  log.debug('running job "%s" for scheduler "%s"', jobID, schedulerID)
  Scheduler.registry[schedulerID]._runJob(jobID, task)

#------------------------------------------------------------------------------
def housekeeping(schedulerID):
  log.debug('starting housekeeping for scheduler "%s"', schedulerID)
  Scheduler.registry[schedulerID]._housekeeping()

#------------------------------------------------------------------------------
class Scheduler(object):

  #: the amount of time to add to **now** in order to ensure that a
  #: `date` job that is scheduled for now does not get refused. this
  #: is to work around an APS "peculiarity" that does not allow a job
  #: to be scheduled for now, as in *right* *now*...
  TIMEPAD = 0.01

  #: if no queue names are specified, `DEFAULT_QUEUE` is the name
  #: given to the one and only queue that will be created.
  DEFAULT_QUEUE = 'default'

  registry = dict()

  #----------------------------------------------------------------------------
  def __init__(self, settings=None, appreg=None, **kw):
    self._listeners = []
    self.id         = None
    self.conf       = adict()
    self.aps        = None
    self.ramstore   = 'internal.transient.' + makeID()
    self.appreg     = appreg
    if settings is not None:
      self.configure(settings, **kw)

  #----------------------------------------------------------------------------
  def configure(self, settings, prefix='scheduler.'):
    self.confdict = conf = combine_opts(settings, prefix)
    self.conf.combined     = asbool(conf.get('combined', True))
    self.conf.housekeeping = asdur(conf.get('housekeeping', '24h'))
    self.conf.hkpostcall   = resolve(conf.get('housekeeping.append', None))
    self.conf.queues       = aslist(conf.get('queues', ''))
    self.conf.grace        = int(conf.get('misfire_grace_time', 1))
    self.id                = conf.get('id', ';'.join(self.conf.queues))
    if len(self.conf.queues) <= 0:
      self.conf.queues = [self.DEFAULT_QUEUE]
    self.broker = broker.Engine(self, conf)
    self.registry[self.id] = self

  #----------------------------------------------------------------------------
  def startProducer(self):
    '''
    Enables this scheduler to "produce" (i.e. create) jobs - must be
    called prior to any calls to the
    `add_(async|date|interval|cron)_job()` methods. Any number of
    schedulers can be started as "producers".
    '''
    pass

  #----------------------------------------------------------------------------
  def startConsumer(self, daemon=True, queues=[]):
    '''
    Enables this scheduler to "consume" (i.e. execute)
    jobs. Currently, this method must be called only **ONCE** for any
    given queue, as it will launch a thread that actually executes the
    jobs. The caller is in charge of ensuring this concurrency
    limitation; it is therefore recommended that `pscheduler` be used
    with a process manager (such as `supervisor
    <http://cr.yp.to/daemontools.html>`_) in conjunction with the
    configuration `scheduler.combined` set to `false`.

    :param daemon:

      Specifies whether or not the thread created for the consumer
      will be set to a daemon thread, i.e. if True (the default), it
      will stop as soon as the main and all non-daemon threads have
      stopped.
    '''
    self.broker.startConsumer(queues)
    log.info('starting APS job execution daemon')
    self.aps = apscheduler.scheduler.Scheduler()
    self.aps.add_jobstore(RAMJobStore(), self.ramstore)
    apsconf = addPrefix(self.confdict, 'apscheduler.')
    apsconf['apscheduler.standalone'] = 'false'
    self.aps.configure(apsconf, daemonic=daemon)
    self.aps.add_interval_job(housekeeping, args=(self.id,),
                              seconds=self.conf.housekeeping, jobstore=self.ramstore)
    self.aps.add_listener(self._apsEvent)
    self.aps.start()

  #----------------------------------------------------------------------------
  def shutdown(self):
    '''
    Shutdown any active producer/consumer threads and/or processes.
    '''
    # todo: shutdown the self.broker and self.aps...
    pass

  #----------------------------------------------------------------------------
  def _apsError(self, event):
    def getJid(event):
      try:    return event.job.id
      except: return None
    log.error('job ID "%s" failed', getJid(event),
              exc_info=event.exception, extra=dict(job=event.job))
    # todo: self._notify?

  #----------------------------------------------------------------------------
  def _apsEvent(self, event):
    if getattr(event, 'exception', None) is not None:
      return self._apsError(event)
    if event.code in (
      apscheduler.events.EVENT_SCHEDULER_START,
      apscheduler.events.EVENT_SCHEDULER_SHUTDOWN,
      apscheduler.events.EVENT_JOBSTORE_ADDED,
      apscheduler.events.EVENT_JOBSTORE_REMOVED,
      #apscheduler.events.EVENT_JOBSTORE_JOB_ADDED,
      #apscheduler.events.EVENT_JOBSTORE_JOB_REMOVED,
      #apscheduler.events.EVENT_JOB_EXECUTED,
      #apscheduler.events.EVENT_JOB_ERROR,
      #apscheduler.events.EVENT_JOB_MISSED,
      ):
      # these can be ignored
      return
    if isinstance(event, apscheduler.events.JobStoreEvent) \
        and event.alias == self.ramstore:
      # this is an "internal" event... squelch it.
      return
    if event.code == apscheduler.events.EVENT_JOBSTORE_JOB_ADDED \
        and hasattr(event, 'job'):
      return self._notify(api.Event(api.Event.JOB_CREATED, job=event.job))
    if event.code == apscheduler.events.EVENT_JOB_EXECUTED:
      return self._notify(api.Event(api.Event.JOB_EXECUTED, job=event.job))
    if event.code == apscheduler.events.EVENT_JOBSTORE_JOB_REMOVED \
        and hasattr(event, 'job'):
      return self._notify(api.Event(api.Event.JOB_REMOVED, job=event.job))
    # todo: any other messages that i should pass through?
    # print 'APS.EVENT:',repr(event)

  #----------------------------------------------------------------------------
  def addListener(self, listener, events=None, args=None, kwargs=None):
    '''
    Adds the callable `listener` to be notified of the events listed
    in `events`, which is a list of constants from
    :class:`pyramid_scheduler.api.Event` that the listener is
    interested in receiving notifications for. Settings `events` to
    None (the default) is equivalent to listening to all
    events. `args` and `kwargs` will be passed to `listener` after the
    first parameter, the :class:`pyramid_scheduler.api.Event` itself.

    Several important notes to be aware of:

    * These events will only be triggered in the process that
      called :meth:`startConsumer`.

    * The listeners will be called from the scheduler thread, so keep
      callback duration to a minimum (this restriction may be lifted
      later by creating a new thread for notification dispatch).

    * The listeners will NOT be called from within a pyramid
      transaction, so if transaction context is needed (i.e. database
      access), create one, e.g.::

        import transaction
        def listener(event, *args, **kw):
          with transaction.manager:
            # ...
    '''
    # todo: mutex?
    self._listeners.append((listener, events, args, kwargs))

  #----------------------------------------------------------------------------
  def removeListener(self, listener):
    '''
    Removes the callable `listener` from receiving any further event
    notifications.
    '''
    # todo: mutex?
    self._listeners = [l for l in self._listeners if l[0] is not listener]

  #----------------------------------------------------------------------------
  def _notify(self, event):
    # todo: mutex?
    for sub in self._listeners:
      if sub[1] is not None and event.type not in sub[1]:
        continue
      try:
        sub[0](event, *sub[2] or [], **sub[3] or {})
      except Exception:
        log.exception('notifying listener %r of event %r failed')

  #----------------------------------------------------------------------------
  def _getdt(self, ts, asStart=False, grace=None):
    if not ts:
      return ts
    if not asStart:
      if isinstance(ts, int) or isinstance(ts, float):
        return ts2dt(ts)
      return ts
    if not ( isinstance(ts, int) or isinstance(ts, float) ):
      ts = dt2ts(ts)
    if ts > ( now() + self.TIMEPAD ):
      return ts2dt(ts)
    if grace is None:
      grace = self.conf.grace
    if ts < ( now() - grace ):
      return ts2dt(ts)
    return ts2dt(now() + self.TIMEPAD)

  #----------------------------------------------------------------------------
  def _handleEvent(self, event):
    if event.type == api.Event.MESSAGE:
      log.debug('received message event: %s', event.message)
      if event.message == 'print-jobs' and self.aps:
        return self.aps.print_jobs()
      return self._notify(event)
    if event.type == api.Event.JOB_CREATED:
      return self._handleEventCreated(event)
    if event.type == api.Event.JOB_CANCELED:
      return self._handleEventCanceled(event)
    log.error('unhandled event: %r', event)

  #----------------------------------------------------------------------------
  def _handleEventCreated(self, event):
    if not self.aps:
      return
    job = event.job
    # APS has this silly bug where if i schedule a job for 'now' it
    # refuses to run it with "ValueError('Not adding job since it
    # would never be run')" -- so the _getdt() calls are to work around
    # that...
    params = job.options
    if 'start_date' in params:
      params.start_date = self._getdt(params.start_date, asStart=True, grace=params.misfire_grace_time)
    if job.type == 'async':
      # todo: make this thread's profile match the ones created by APScheduler...
      thread = threading.Thread(
        target = pyramid_scheduler_wrapper,
        args   = (self.id, job.id, job.task),
      )
      thread.daemon = True
      thread.start()
      return
    if job.type == 'date':
      params.date = self._getdt(params.date, asStart=True, grace=params.misfire_grace_time)
      self.aps.add_date_job(
        pyramid_scheduler_wrapper,
        args=(self.id, job.id, job.task), **params)
      return
    if job.type == 'interval':
      self.aps.add_interval_job(
        pyramid_scheduler_wrapper,
        args=(self.id, job.id, job.task), **params)
      return
    if job.type == 'cron':
      self.aps.add_cron_job(
        pyramid_scheduler_wrapper,
        args=(self.id, job.id, job.task), **params)
      return
    log.error('unknown job scheduling type "%s" in event: %r', job.type, event)

  #----------------------------------------------------------------------------
  def _handleEventCanceled(self, event):
    if not self.aps:
      return
    job = event.job
    if not job.id:
      log.error('received request to cancel unidentified job: %r', job)
      return
    jobs = [j for j in self.aps.get_jobs() if j.id == job.id]
    if not jobs:
      log.warning('received request to cancel unknown job: %r', job)
      return
    for apsjob in jobs:
      self.aps.unschedule_job(apsjob)
      self._notify(api.Event(api.Event.JOB_CANCELED, job=apsjob))

  #----------------------------------------------------------------------------
  @contextmanager
  def _threadContext(self):
    # IMPORTANT: this assumes that APScheduler invokes jobs in a separate
    #            thread per job (as documented)...
    # TODO: this needs confirmation!
    if self.appreg is None:
      yield
    else:
      from pyramid.threadlocal import manager
      reg = dict(manager.get())
      reg['registry'] = self.appreg
      manager.push(reg)
      try:
        yield
      finally:
        manager.pop()

  #----------------------------------------------------------------------------
  def _runJob(self, jobID, task):
    with self._threadContext():
      # TODO: ensure proper transaction handling
      with transaction.manager:
        func = ref_to_obj(task.func)
        func(*task.args or [], **task.kwargs or {})

  #----------------------------------------------------------------------------
  def _housekeeping(self):
    with self._threadContext():
      # TODO: do housekeeping:
      #         - delete old kombu messages (can't they be auto-delete???)
      if self.conf.hkpostcall:
        self.conf.hkpostcall()

  #----------------------------------------------------------------------------
  def add_async_job(self, func, args=None, kwargs=None, queue=None, **options):
    '''
    Adds an asynchronous job -- identical to calling :meth:`add_date_job` with
    `date` set to the current time (i.e. ``time.time()``).

    Note that this job will appear in the scheduler's job list
    *asynchronously*, i.e. only after some undefined (but short, if
    everything is working correctly) period of time.

    :Returns:

    str
      The identifier for the job.
    '''
    return self._add(func, args, kwargs, queue, 'async', options)

  #----------------------------------------------------------------------------
  def add_date_job(self, func, date, args=None, kwargs=None, queue=None, **options):
    '''
    Schedules the function `func` to be run once on the specified
    `date`, which can be either a datetime (`datetime.datetime`)
    instance or epoch timestamp (int or float). The function will be
    called with positional parameters specified by `args` and keyword
    parameters `kwargs`, both of which must be pickleable via
    `pickle.dumps()` using the highest protocol available. The
    function `func` must be a static module-level function; it
    therefore must not be an anonymous or lambda function, class or
    instance method.

    You can also specify a `queue` that this job should be scheduled
    on, which must be one of the queues defined in the
    pyramid-scheduler configuration. If not specified, it defaults to
    the first specified queue.

    Any of the additional parameters supported by
    :class:`apscheduler.scheduler.Scheduler` are also supported
    in blind pass-through mode.

    Note that this job will appear in the scheduler's job list
    *asynchronously*, i.e. only after some undefined (but short, if
    everything is working correctly) period of time.

    :Returns:

    str
      The identifier for the job.
    '''
    return self._add(func, args, kwargs, queue, 'date',
                     cull(**adict(date=date).update(options)))

  #----------------------------------------------------------------------------
  def add_interval_job(self, func, start_date=None, args=None, kwargs=None, queue=None,
                       weeks=0, days=0, hours=0, minutes=0, seconds=0,
                       **options):
    '''
    A repeating interval-oriented version of :meth:`add_date_job` --
    see :meth:`apscheduler.scheduler.Scheduler.add_interval_job` for
    additional documentation.

    :Returns:

    str
      The identifier for the job.
    '''
    seconds += ( weeks * 604800 ) + ( days * 86400 ) + ( hours * 3600 ) + ( minutes * 60 )
    return self._add(func, args, kwargs, queue, 'interval',
                     cull(**adict(start_date=start_date, seconds=seconds).update(options)))

  #----------------------------------------------------------------------------
  def add_cron_job(self, func, start_date=None, args=None, kwargs=None, queue=None,
                   year=None, month=None, day=None, week=None, day_of_week=None,
                   hour=None, minute=None, second=None, **options):
    '''
    A cron-like version of :meth:`add_date_job` -- see
    :meth:`apscheduler.scheduler.Scheduler.add_cron_job` for
    additional documentation.

    :Returns:

    str
      The identifier for the job.
    '''
    return self._add(func, args, kwargs, queue, 'cron',
                     cull(**adict(start_date=start_date, year=year, month=month,
                                  day=day, week=week, day_of_week=day_of_week,
                                  hour=hour, minute=minute, second=second).update(options)))

  #----------------------------------------------------------------------------
  def _add(self, func, args, kwargs, queue, ftype, fargs):
    queue = queue or self.conf.queues[0]
    if queue not in self.conf.queues:
      raise api.InvalidQueue(queue)
    event = api.Event(
      api.Event.JOB_CREATED,
      queue = queue,
      job   = adict(
        id      = makeID(),
        type    = ftype,
        options = adict(fargs),
        task    = adict(
          func    = obj_to_ref(func),
          args    = args,
          kwargs  = kwargs,
        )
      )
    )
    self.broker.send(event, queue)
    return event.job.id

  #----------------------------------------------------------------------------
  def cancel_job(self, jobID, queue=None):
    '''
    Cancels the job with the ID `jobID` (as returned by any of the
    `add_(async|date|interval|cron)_job()` methods). If `queue` is not
    specified, it is removed from all queues. Note that the execution
    of this request is *asynchronous*.
    '''
    if queue and queue not in self.conf.queues:
      raise api.InvalidQueue(queue)
    event = api.Event(api.Event.JOB_CANCELED, job=adict(id=jobID))
    self.broker.send(event, queue)


#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

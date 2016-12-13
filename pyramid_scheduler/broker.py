# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# lib:  pyramid_scheduler.broker
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/04/15
# copy: (C) Copyright 2013 Cadit Inc., see LICENSE.txt
#------------------------------------------------------------------------------

'''
The `pyramid_scheduler.broker` module deals with the communication
between job producers and job executers (consumers). The default
implementation uses `kombu` as the underlying engine.
'''

import time, logging, threading
import kombu, kombu.pools, kombu.common
from kombu.mixins import ConsumerMixin
import six

from . import api
from .util import adict

log = logging.getLogger(__name__)

#------------------------------------------------------------------------------
class KombuWorker(ConsumerMixin):
  def __init__(self, engine, connection):
    self.engine     = engine
    self.connection = connection
  def get_consumers(self, Consumer, channel):
    return [Consumer(
      queues    = self.engine.queues,
      callbacks = [self.event],
      accept    = ['pickle'],
    )]
  def event(self, event, message):
    log.debug('received message: %r', event)
    self.engine.scheduler._handleEvent(event)
    message.ack()

#------------------------------------------------------------------------------
class Engine(object):

  #----------------------------------------------------------------------------
  def __init__(self, scheduler, conf):
    self.scheduler  = scheduler
    self.thread     = None
    self.exchange   = kombu.Exchange('pyramid_scheduler', type='topic')
    self.queues     = [
      kombu.Queue(queue, exchange=self.exchange, routing_key=queue)
      for queue in scheduler.conf.queues]
    self.connection = kombu.Connection(conf.get('broker.url'))
    self.serializer = conf.get('broker.serializer', 'pickle')
    # note: disabling compression for PY3 since kombu 2.5.10 fails
    #       with pickle+bzip2...
    # todo: remove this workaround when kombu is fixed...
    self.compressor = conf.get('broker.compressor', None if six.PY3 else 'bzip2')

  #----------------------------------------------------------------------------
  def send(self, message, queue=None):
    if isinstance(message, six.string_types):
      message = api.Event('message', message=message)
    if not isinstance(message, api.Event):
      raise api.InvalidMessage('broker messages must be instances of'
                               ' pyramid_scheduler.api.Event, not %s: %r' %
                               (type(message), message,))
    self._send(queue, message)

  #----------------------------------------------------------------------------
  def startConsumer(self, queues):
    if queues:
      log.warning('queue selection list is specified but not supported yet -- ignoring')
    # TODO: implement use of `queues`...
    self.thread = threading.Thread(target=self._run)
    self.thread.daemon = True
    self.thread.start()

  #----------------------------------------------------------------------------
  def _run(self):
    while True:
      try:
        log.debug('acquiring event consumer')
        with kombu.pools.connections[self.connection].acquire(block=True) as conn:
          try:
            KombuWorker(self, conn).run()
          except Exception:
            log.exception('scheduler event consumer failed during connection handling')
      except Exception:
        log.exception('scheduler event consumer failed to acquire/listen to a connection')
        time.sleep(5)

  #----------------------------------------------------------------------------
  def _send(self, queue, payload):
    if not queue:
      for q in [q.name for q in self.queues]:
        self._send(q, payload)
      return
    if queue not in [q.name for q in self.queues]:
      raise api.InvalidQueue(queue)
    log.debug('sending message %r to %s', payload, queue)
    with kombu.pools.producers[self.connection].acquire(block=True) as producer:
      kombu.common.maybe_declare(self.exchange, producer.channel)
      producer.publish(
        payload,
        serializer   = self.serializer,
        compression  = self.compressor,
        exchange     = self.exchange,
        routing_key  = queue,
        declare      = self.queues,
      )

#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

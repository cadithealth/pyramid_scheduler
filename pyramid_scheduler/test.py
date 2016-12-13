# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------
# file: $Id$
# auth: Philip J Grabner <grabner@cadit.com>
# date: 2013/12/18
# copy: (C) Copyright 2013-EOT Cadit Inc., All Rights Reserved.
#------------------------------------------------------------------------------

import os
import unittest
import tempfile
import shutil
import sqlalchemy as sa
import json
import uuid
import webtest
import time
import threading
import kombu.transport.sqlalchemy.models as ksam
from kombu.transport.sqlalchemy.models import metadata, Queue, Message
from pyramid.config import Configurator
from pyramid.response import Response

#------------------------------------------------------------------------------
storedData = []
storedDataCond = threading.Condition()
def store_some_data(**data):
  with storedDataCond:
    storedData.append(data)
    storedDataCond.notify()

#------------------------------------------------------------------------------
def ReflectorApp(settings={}):
  engine = sa.engine_from_config(settings, 'sqlalchemy.')
  config = Configurator(settings=settings)
  def reflect_params(request):
    return Response(json.dumps(dict(request.params)))
  def deferred_store_params(request):
    request.registry.scheduler.add_date_job(
      store_some_data, time.time() + 0.5, kwargs=dict(request.params))
    return Response('ok')
  config.add_route('reflect', '/reflect/*path')
  config.add_view(reflect_params, route_name='reflect')
  config.add_route('deferred', '/store/*path')
  config.add_view(deferred_store_params, route_name='deferred')
  return config.make_wsgi_app()

#------------------------------------------------------------------------------
class TestScheduler(unittest.TestCase):

  #----------------------------------------------------------------------------
  @classmethod
  def setUpClass(klass):
    # create a master database
    fp = tempfile.NamedTemporaryFile(
      suffix='.db', prefix='pyramid_scheduler-unittest-master-', delete=False)
    klass.masterdb_path = fp.name
    fp.close()
    engine = sa.create_engine('sqlite:///' + klass.masterdb_path)
    # kombu 3.0.8 compat
    if hasattr(ksam, 'class_registry'):
      class Queue(ksam.Queue, ksam.ModelBase):
        __tablename__ = 'kombu_queue'
      class Message(ksam.Message, ksam.ModelBase):
        __tablename__ = 'kombu_message'
    metadata.create_all(engine)
    # todo: any other default things?...
    # TODO: this is a hack. fix! for some reason, when auto-inserting the
    #       queue names, i *sometimes* get the following error:
    #         IntegrityError: (IntegrityError) column name is not unique
    #         u'INSERT INTO kombu_queue (name) VALUES (?)' ('test-queue',)
    engine.execute("INSERT INTO kombu_queue (name) VALUES ('test-queue')")

  #----------------------------------------------------------------------------
  @classmethod
  def tearDownClass(klass):
    os.unlink(klass.masterdb_path)

  #----------------------------------------------------------------------------
  def setUp(self):
    # replicate the master database and create a test application
    fp = tempfile.NamedTemporaryFile(
      suffix='.db', prefix='pyramid_scheduler-unittest-replica-', delete=False)
    self.dbpath = fp.name
    self.dburl  = 'sqlite:///' + self.dbpath
    fp.close()
    shutil.copyfile(self.masterdb_path, self.dbpath)

  #----------------------------------------------------------------------------
  def tearDown(self):
    os.unlink(self.dbpath)

  #----------------------------------------------------------------------------
  def initApp(self, **settings):
    appset = {
      'sqlalchemy.url'        : self.dburl,
      'pyramid.includes'      : 'pyramid_scheduler',
      'scheduler.combined'    : 'true',
      'scheduler.queues'      : 'test-queue',
      'scheduler.broker.url'  : 'kombu.transport.sqlalchemy:Transport+' + self.dburl,
    }
    appset.update(settings or {})
    self.app     = ReflectorApp(settings=appset)
    self.testapp = webtest.TestApp(self.app)

  #----------------------------------------------------------------------------
  def test_testapp(self):
    self.initApp()
    res = self.testapp.get('/reflect/params/?hello=world')
    self.assertEqual(res.body, b'{"hello": "world"}')
    val = str(uuid.uuid4())
    res = self.testapp.get('/reflect/params/?value=' + val)
    self.assertEqual(res.body, b'{"value": "' + val.encode('ascii') + b'"}')

  #----------------------------------------------------------------------------
  def test_kombu308_newSerializerDefault(self):
    self.initApp()
    self.assertEqual(storedData, [])
    val = str(uuid.uuid4())
    res = self.testapp.get('/store/?val=' + val)
    self.assertEqual(res.body, b'ok')
    with storedDataCond:
      if not storedData:
        storedDataCond.wait(timeout=3)
      self.assertEqual(storedData, [{'val': val}])


#------------------------------------------------------------------------------
# end of $Id$
# $ChangeLog$
#------------------------------------------------------------------------------

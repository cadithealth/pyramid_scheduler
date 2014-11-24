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

import sys

import logging
log = logging.getLogger(__name__)
logging.basicConfig()

#------------------------------------------------------------------------------
storedData = []
storedDataCond = threading.Condition()
def store_some_data(**data):
  with storedDataCond:
    storedData.append(data)
    storedDataCond.notify()

#------------------------------------------------------------------------------
def execute_some_func(**data):
  return True

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
  def interval_store_params(request):
    job_id = request.registry.scheduler.add_interval_job(
      execute_some_func, minutes=1, kwargs=dict(request.params))
    #return Response('ok')
    return Response(str(job_id))
  def cancel_store_params(request):
    job_id = request.params.get('val')
    request.registry.scheduler.cancel_job(job_id)
    return Response('ok')
  def get_stored_jobs(request):
    jobs = request.registry.scheduler.get_jobs()
    clean_jobs = []
    for job in jobs:
        job.pop('_lock', "")
        job.pop('next_run_time', "")
        job.pop('trigger', "")
        job['func'] = str(job['func'])
        clean_jobs.append(job)
    return Response(json.dumps(clean_jobs))
  config.add_route('reflect', '/reflect/*path')
  config.add_view(reflect_params, route_name='reflect')
  config.add_route('deferred', '/store/*path')
  config.add_view(deferred_store_params, route_name='deferred')
  config.add_route('interval', '/execute/*path')
  config.add_view(interval_store_params, route_name='interval')
  config.add_route('get', '/return/*path')
  config.add_view(get_stored_jobs, route_name='get')
  config.add_route('cancel', '/cancel/*path')
  config.add_view(cancel_store_params, route_name='cancel')
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
    try:
        os.unlink(klass.masterdb_path)
        sys.exit()
    except:
        pass

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
    storedData = []

  #----------------------------------------------------------------------------
  def tearDown(self):
    try:
        os.unlink(self.dbpath)
    except:
        pass

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

  #----------------------------------------------------------------------------
  def test_scheduler_cancel_job(self):
    self.initApp()
    # Start and verify only housekeeping job is currently in the queue
    resp = self.testapp.get('/return/?val=')
    jobs = json.loads(resp.body)
    self.assertEquals(len(jobs), 1)
    self.assertEquals(jobs[0]['name'], 'housekeeping')
    val = str(uuid.uuid4())
    # Add new scheduled job to the queue
    res = self.testapp.get('/execute/?val=' + val)
    job_id = res.body
    time.sleep(2)
    # Verify new scheduled job is added to the queue
    resp = self.testapp.get('/return/?val=')
    jobs = json.loads(resp.body)
    self.assertEquals(len(jobs), 2)
    # Cancel the new scheduled job
    resp = self.testapp.get('/cancel/?val='+job_id)
    time.sleep(2)
    # Verify only housekeeping job is currently in the queue
    resp = self.testapp.get('/return/?val=' + val)
    jobs = json.loads(resp.body)
    self.assertEquals(len(jobs), 1)
    self.assertEquals(jobs[0]['name'], 'housekeeping')

#------------------------------------------------------------------------------
# end of $Id$
#------------------------------------------------------------------------------

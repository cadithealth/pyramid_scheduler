=================
pyramid_scheduler
=================

The ``pyramid-scheduler`` package is a pyramid plugin that allows
asynchronous and deferred task scheduling and management. It uses
APScheduler_ for actual task management and Kombu_ for messaging
between processes.

**IMPORTANT**: the pyramid-scheduler is very new, but fully
functional. The following features are considered "beta", and
should probably not be used in production:

* Multiple queues. For now, just use a single queue (and thus you are
  limited to a single background process).

* Intuitive sequence of job events. Currently, the events that can be
  listened to (from pyramid_scheduler.api.Event, such as JOB_CREATED,
  JOB_EXECUTED, JOB_CANCELED, and JOB_REMOVED) do not reliably fire in
  an intuitive order. For example, you may get a JOB_REMOVED event
  before the JOB_EXECUTED event for a deferred job.


TL;DR
=====

Install:

.. code-block:: bash

  $ pip install pyramid-scheduler

Use:

.. code-block:: python

  # ini file settings:
  #   [app:main]
  #   scheduler.combined   = true | false   ## should execution be in-process?
  #   scheduler.queues     = jobs           ## space-separated list of queues
  #   scheduler.broker.url = %(dburl)s      ## the URL used for kombu messaging
  #   ## other optional settings:
  #   ##   scheduler.housekeeping
  #   ##   scheduler.housekeeping.append
  #   ##   scheduler.jobstore.default.class
  #   ##   scheduler.misfire_grace_time

  # enabling the plugin adds a `scheduler` attribute to the registry
  def main(global_config, **settings):
    # ... (the usual pyramid startup calls) ...
    config.include('pyramid_scheduler)

  # create an asynchronous task
  def slow_process(name, id):
    # ...a slow asynchronous job...
  def handle_request_quickly(request):
    request.registry.scheduler.add_async_job(slow_process, args=('my-first-arg', 2))

  # schedule a deferred task for one hour from now
  def delayed_process():
    # ...something that should happen later...
  def handle_request_now(request):
    import time
    request.registry.scheduler.add_date_job(delayed_process, time.time() + 3600)

  # do something every 10 minutes
  def interval_process(reason=None):
    # ...gets executed every 10 minutes with an optional reason...
  def handle_request_often(request):
    request.registry.scheduler.add_date_job(interval_process, minutes=10)


Concepts
========

The pyramid-scheduler package refers to asynchronous or deferred tasks
to be managed as "jobs" and these fall into the following categories:

* Asynchronous jobs:

  These jobs are executed immediately, but asynchronously.

* Deferred jobs, i.e. "date" jobs:

  Jobs that are scheduled to be performed at a specific time.

* Interval jobs:

  Similar to deferred jobs, but that are then re-executed on an
  interval.

* Cron jobs:

  Similar to interval jobs, but they use a scheduling definition
  that is similar to a unix "cron" definition.

Conceptually, there are two activities: the activity of creating the
jobs and the activity of executing the jobs. These can be performed by
the same process (with "combined" mode enabled), or they can be
performed by different processes (with "combined" mode disabled).

If there are multiple processes that are creating jobs (for example,
if your are running multiple servers or your WSGI configuration uses
multiple processes), then you **CANNOT** run pyramid-scheduler in
combined mode since then there will be multiple processes executing
the jobs leading to multiple executions.

Typically, combined mode is used during development where a single
`pserve` instance will be used. Then, in production mode, you will
have multiple servers and WSGI processes that generate jobs, that
are then executed by a single background process (managed via the
`pscheduler` daemon).

Pyramid-scheduler supports multiple "queues". The main reason to use
separate queues is that the `pscheduler` can be configured to only
process jobs for specific queues, which means that multiple
pschedulers can work in parallel as long as they are listening to
different queues. (A later enhancement is planned to allow multiple
pschedulers to handle a single queue.)

**IMPORTANT**: currently, the following limitations exist:

* The callback handler provided as the first argument to the scheduler
  add_*_job() methods must be a normal module-level defined
  function. It *cannot* be a lambda function, an internal function, a
  method, or otherwise function that is not globally resolvable using
  standard dot-notation.

* The `args` and `kwargs` parameters must all be completely
  pickle-able.

* Deferred jobs that are scheduled to occur further in the past than
  `misfire_grace_time` will be silently dropped.

* Jobs that take a `date` or `start_date` parameter can specify those
  values either as an epoch int or float or as a datetime object. If
  a datetime is provided, it **must** be timezone "naive" (see the
  documentation of datetime_).

Under the hood, pyramid-scheduler uses APScheduler to do the actual
processing and scheduling. For messaging between the job creators and
the pscheduler background process, it uses Kombu messaging, which
supports a variety of transports including Redis and SQLAlchemy. This
package was developed as an alternative to celery, due to severe
limitations found in the celery API and shortcomings in the actual
implementation.


Installation
============

You can manually install it by running:

.. code-block:: bash

  $ pip install pyramid-scheduler

However, a better approach is to use standard python distribution
utilities, and add pyramid-scheduler as a dependency in your project's
`install_requires` parameter in your ``setup.py``. Then run a ``python
setup.py develop``.

Then, enable the package either in your INI file via:

.. code-block:: text

  pyramid.includes = pyramid_scheduler

or in code in your package's application initialization via:

.. code-block:: python

  def main(global_config, **settings):
    # ...
    config.include('pyramid_scheduler')
    # ...


Configuration
=============

The following configuration options (placed in the "[app:main]"
section of your INI file):

TODO: add documentation

* scheduler.combined
* scheduler.queues
* scheduler.broker.url
* scheduler.broker.serializer
* scheduler.broker.compressor
* scheduler.housekeeping
* scheduler.housekeeping.append
* scheduler.jobstore.default.class
* scheduler.misfire_grace_time


Debugging
=========

The first step in debugging a pyramid-scheduler instance is to elevate
the logging, and that is easiest via the application
configuration. Here, an example that increases logging to DEBUG level
and sends the logs to STDERR:

.. code-block:: ini

   [loggers]
   keys               = scheduler, ...

   [handlers]
   keys               = console, ...

   [formatters]
   keys               = generic, ...

   [logger_scheduler]
   level              = DEBUG
   handlers           = console
   qualname           = pyramid_scheduler

   [handler_console]
   class              = StreamHandler
   args               = (sys.stderr,)
   level              = NOTSET
   formatter          = generic

   [formatter_generic]
   format             = %(levelname)-5.5s [%(name)s] %(message)s


If that does not expose the source of the problem, you can take some
of the following actions:

Confirm Communication
---------------------

You can confirm that the task producers and consumers are
communicating by sending a ``print-jobs`` message. First, check
the configurations by sending the message from a fake producer
by using the ``pscheduler --message`` feature as follows:

.. code-block:: bash

   $ pscheduler --message 'print-jobs' {CONFIG}.ini

   DEBUG [pyramid_scheduler.pscheduler] loading application from "{CONFIG}.ini"
   DEBUG [pyramid_scheduler.broker] sending message <pyramid_scheduler.api.Event message={'message': 'print-jobs'}> to messenger

and you should see something like this in the pscheduler daemon logs
(depending on what happens to STDOUT, you may only see the DEBUG
messages, not the actual Jobstore messages):

.. code-block:: text

  DEBUG [pyramid_scheduler.broker] received message: <pyramid_scheduler.api.Event message={'message': 'print-jobs'}>
  DEBUG [pyramid_scheduler.scheduler] received message event: print-jobs
  Jobstore default:
      pyramid_scheduler_wrapper (trigger: cron[hour='0', minute='5'], next run at: 2014-12-03 00:05:00)
  Jobstore internal.transient.8524480f-26b4-4a69-8bcd-3bb180d0cf9e:
      housekeeping (trigger: interval[1 day, 0:00:00], next run at: 2014-12-03 14:45:26.696818)

If that does not work, you need to check the application
configurations, both on the consumer and producer sides. You may also
need to debug the Kombu_ sub-system.

TODO: add documentation


Task Execution Process
======================

There are several ways that the tasks in a queue can actually be
executed. The preferred way, described here, is to use the
`pscheduler` script which is intended to be run in daemon mode by a
daemon-running service, such as DJB's daemontools_ package.

Install daemontools (adjust for your package manager):

.. code-block:: bash

  $ apt-get install daemontools

This should install & start the `svscan` monitoring against the
``/etc/service`` directory. You can do a `ps` to confirm this, and if
it is not running, read the daemontools docs. If it is scanning a
directory other than ``/etc/service``, adjust the following examples
appropriately.

Create & configure the logging subsystem by creating the following
file in ``/etc/service/pscheduler/log/run`` (where ``pscheduler`` can
be whatever you want). This example will store up to 100MiB of logs
in the ``/var/log/pscheduler`` directory:

.. code-block:: text

  #!/bin/sh
  exec multilog t s10485760 n10 /var/log/pscheduler

Create & configure the `pscheduler` service by creating the following
file in ``/etc/service/pscheduler/run`` (where ``pscheduler`` can be
whatever you want). This example will run `pscheduler` as the
``www-data`` user (it is simplest if it runs as the same user as the
appserver that is producing pyramid-scheduler tasks):

.. code-block:: text

  #!/bin/sh
  exec env -i PATH="/bin:/usr/bin:$PATH" \
  setuidgid www-data \
  /path/to/virtualenv/bin/pscheduler \
    /path/to/config.ini \
  2>&1

And ensure that both files are executable:

.. code-block:: bash

  $ chmod 755 /etc/service/pscheduler/log/run
  $ chmod 755 /etc/service/pscheduler/run


.. _APScheduler: https://pypi.python.org/pypi/APScheduler
.. _Kombu: https://pypi.python.org/pypi/kombu
.. _datetime: http://docs.python.org/2/library/datetime.html
.. _daemontools: http://cr.yp.to/daemontools.html

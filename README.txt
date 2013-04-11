pyramid_scheduler
=================

A pyramid plugin that allows asynchronous and deferred task scheduling
and management.

**IMPORTANT**: this plugin is currently in development and not
available yet - check back in a few weeks...

When ready, pyramid-scheduler will allow multiple pyramid WSGI
threads, processes, and servers to schedule tasks to be executed in a
separate background process (managed via the ``pscheduler`` daemon)
which may or may not be on the same machine.

In the background process, it will use APScheduler. It will use an
abstract storage interface for messaging so that it can be extended to
support any backend (such as Redis), but in the initial implementation
will use SQLAlchemy with postgres' pub/sub interface.

This package is being developed as an alternative to celery, due to
severe limitations found in the API. If you are willing to use Redis
and/or do not need to cancel or revise active tasks, you should use
celery. If you do not need execution in a separate process, you should
use APScheduler directly.

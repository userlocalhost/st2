# Monkey patching should be done as early as possible.
# See http://eventlet.net/doc/patching.html#monkeypatching-the-standard-library
from __future__ import absolute_import
from st2common.util.monkey_patch import monkey_patch
monkey_patch()

import os
import signal
import sys

from st2actions.scheduler import config
from st2common import log as logging
from st2common.service_setup import teardown as common_teardown
from st2common.service_setup import setup as common_setup

__all__ = [
    'main'
]

LOG = logging.getLogger(__name__)


def _setup_sigterm_handler():
    def sigterm_handler(signum=None, frame=None):
        # This will cause SystemExit to be throw and allow for component cleanup.
        sys.exit(0)

    # Register a SIGTERM signal handler which calls sys.exit which causes SystemExit to
    # be thrown. We catch SystemExit and handle cleanup there.
    signal.signal(signal.SIGTERM, sigterm_handler)


def _setup():
    common_setup(service='scheduler', config=config, setup_db=True, register_mq_exchanges=True,
                 register_signal_handlers=True)
    _setup_sigterm_handler()


def _run_queuer():
    LOG.info('(PID=%s) Scheduler started.', os.getpid())

    # Lazy load these so that decorator metrics are in place
    from st2actions.scheduler import (
        handler as scheduler_handler,
        entrypoint as scheduler_entrypoint
    )

    handler = scheduler_handler.get_handler()
    entrypoint = scheduler_entrypoint.get_scheduler_entrypoint()

    try:
        handler.start()
        entrypoint.start()
        entrypoint.wait()
    except (KeyboardInterrupt, SystemExit):
        LOG.info('(PID=%s) Scheduler stopped.', os.getpid())

        errors = False

        try:
            handler.shutdown()
            entrypoint.shutdown()
        except:
            LOG.exception('Unable to shutdown scheduler.')
            errors = True

        if errors:
            return 1
    except:
        LOG.exception('(PID=%s) Scheduler unexpectedly stopped.', os.getpid())
        return 1

    return 0


def _teardown():
    common_teardown()


def main():
    try:
        _setup()
        return _run_queuer()
    except SystemExit as exit_code:
        sys.exit(exit_code)
    except:
        LOG.exception('(PID=%s) Scheduler quit due to exception.', os.getpid())
        return 1
    finally:
        _teardown()

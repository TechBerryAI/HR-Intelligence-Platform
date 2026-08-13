"""Dedicated integration auto-sync process.

Production (multi-Gunicorn-worker) must run this separately so singleton
scheduled sync executes once per interval:

  gunicorn -c gunicorn.conf.py wsgi:app
  RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger('integrations.scheduler')


def main() -> int:
    # Ensure flag is on even if operator forgot it when using this entrypoint.
    os.environ['RUN_INTEGRATION_AUTO_SYNC'] = '1'
    os.environ['HCIP_PROCESS_ROLE'] = 'scheduler'

    # Load .env the same way wsgi does when present.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from app.domains.integrations.scheduler import (
        start_auto_sync_scheduler,
        stop_auto_sync_scheduler,
    )

    def _shutdown(signum, _frame):
        logger.info('received signal %s — stopping auto-sync', signum)
        stop_auto_sync_scheduler()
        # Give daemon thread a moment to exit the wait
        time.sleep(0.5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info('starting dedicated integration auto-sync scheduler')
    start_auto_sync_scheduler()

    # Keep process alive while daemon thread runs
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    raise SystemExit(main())

"""Dedicated integration outbox drain process.

Web workers already drain via SKIP LOCKED. This entrypoint is the documented
production role for operators who want a dedicated drain process:

  gunicorn -c gunicorn.conf.py wsgi:app
  RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler
  python -m app.domains.integrations.worker
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
logger = logging.getLogger('integrations.outbox')


def main() -> int:
    os.environ.setdefault('HCIP_PROCESS_ROLE', 'outbox')

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from app.domains.integrations.worker.outbox import start_outbox_drain, stop_outbox_drain

    def _shutdown(signum, _frame):
        logger.info('received signal %s — stopping outbox drain', signum)
        stop_outbox_drain(timeout=5.0)
        time.sleep(0.3)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info('starting dedicated integration outbox drain')
    start_outbox_drain()

    while True:
        time.sleep(3600)


if __name__ == '__main__':
    raise SystemExit(main())

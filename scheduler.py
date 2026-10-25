import os
import time
import threading
import logging
from typing import Optional

from monitor import check_all_websites
from database import prune_old_history

logger = logging.getLogger("website_health_monitor.scheduler")

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_running = False
_lock = threading.Lock()


def get_check_interval() -> int:
    """Retrieve check interval from CHECK_INTERVAL env var (default: 60s)."""
    try:
        val = int(os.environ.get("CHECK_INTERVAL", 60))
        return max(val, 10)  # minimum 10 seconds to prevent abuse
    except ValueError:
        return 60


def get_retention_days() -> int:
    """Retrieve history retention period in days from env (default: 30 days)."""
    try:
        val = int(os.environ.get("HISTORY_RETENTION_DAYS", 30))
        return max(val, 1)
    except ValueError:
        return 30


def _background_worker(db_path: Optional[str] = None):
    """Background monitoring loop running on a daemon thread."""
    logger.info("Background monitoring thread started.")
    last_prune_time = 0.0

    while not _stop_event.is_set():
        interval = get_check_interval()
        try:
            # Check all websites
            check_all_websites(db_path=db_path)

            # Once per day, prune old history records
            current_time = time.time()
            if current_time - last_prune_time > 86400:
                retention = get_retention_days()
                pruned = prune_old_history(retention_days=retention, db_path=db_path)
                if pruned > 0:
                    logger.info(f"Pruned {pruned} historical checks older than {retention} days.")
                last_prune_time = current_time

        except Exception as exc:
            logger.error(f"Error during periodic health check run: {exc}", exc_info=True)

        # Sleep in small increments to allow quick shutdown
        for _ in range(interval):
            if _stop_event.is_set():
                break
            time.sleep(1)

    logger.info("Background monitoring thread stopped.")


def start_scheduler(db_path: Optional[str] = None, force: bool = False) -> bool:
    """
    Start the background scheduler thread if not already running.
    Guards against duplicate schedulers in Flask debug reloader.
    """
    global _scheduler_thread, _is_running

    # Guard against starting in Werkzeug reloader parent process
    # Werkzeug sets WERKZEUG_RUN_MAIN='true' in the actual child worker process
    if not force and os.environ.get("FLASK_DEBUG", "").lower() in ("true", "1"):
        if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            logger.debug("Skipping scheduler startup in Werkzeug reloader master process.")
            return False

    with _lock:
        if _is_running and _scheduler_thread and _scheduler_thread.is_alive():
            return False

        _stop_event.clear()
        _scheduler_thread = threading.Thread(
            target=_background_worker,
            args=(db_path,),
            daemon=True,
            name="HealthMonitorScheduler",
        )
        _scheduler_thread.start()
        _is_running = True
        logger.info(f"Scheduler started with {get_check_interval()}s interval.")
        return True


def stop_scheduler() -> None:
    """Signal background thread to stop and wait for it."""
    global _is_running
    with _lock:
        _stop_event.set()
        _is_running = False


def is_scheduler_running() -> bool:
    """Return whether the scheduler is currently active."""
    global _scheduler_thread, _is_running
    return bool(_is_running and _scheduler_thread and _scheduler_thread.is_alive())

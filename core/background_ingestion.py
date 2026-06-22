import logging
import os
from datetime import datetime, timezone
from typing import Any

from core.rag_engine import sync_vector_db

logger = logging.getLogger(__name__)


def run_incremental_ingestion_job() -> dict[str, Any]:
    """
    Background-safe ingestion job for policy document updates.

    The job performs change detection before embedding, using file metadata and
    MD5 hashes managed by `sync_vector_db`. It is intentionally idempotent: if
    no source file changed, no ChromaDB writes occur. This allows the Flask API
    to keep serving read traffic while the worker updates only affected chunks.
    """

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = sync_vector_db()
        logger.info("Incremental ingestion completed: %s", result)
        return {"status": "ok", "started_at": started_at, "result": result}
    except Exception as exc:
        logger.exception("Incremental ingestion failed: %s", exc)
        return {"status": "error", "started_at": started_at, "error": str(exc)}


def start_background_ingestion_scheduler() -> Any | None:
    """
    Start an APScheduler background worker for zero-downtime ingestion.

    This is a structural production hook. In a larger deployment, the same job
    can be moved to a dedicated worker process, Kubernetes CronJob, Celery beat,
    or cloud scheduler without changing the ingestion contract.
    """

    if os.getenv("CIVICEASE_ENABLE_BACKGROUND_INGESTION", "false").lower() != "true":
        logger.info("Background ingestion scheduler disabled.")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler is not installed; background ingestion was not started.")
        return None

    interval_minutes = int(os.getenv("CIVICEASE_INGESTION_INTERVAL_MINUTES", "30"))
    scheduler = BackgroundScheduler(
        timezone=os.getenv("CIVICEASE_SCHEDULER_TIMEZONE", "UTC"),
        daemon=True,
    )
    scheduler.add_job(
        run_incremental_ingestion_job,
        trigger="interval",
        minutes=interval_minutes,
        id="civicease_incremental_ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Background ingestion scheduler started; interval=%s minutes.", interval_minutes)
    return scheduler

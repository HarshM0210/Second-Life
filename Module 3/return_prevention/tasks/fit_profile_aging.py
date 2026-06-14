"""
return_prevention/tasks/fit_profile_aging.py

Background job that transitions stale Fit_Profile rows from 'pending' to 'kept'.

After 30 days without a return event, an order is assumed to have been kept by the
customer. This job runs every hour via APScheduler's BackgroundScheduler and
bulk-updates matching rows.

Requirements: 2.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from return_prevention.db.database import SessionLocal
from return_prevention.db.repositories import FitProfileRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGING_DAYS: int = 30
"""Number of days after which a pending order is considered kept."""

JOB_INTERVAL_HOURS: int = 1
"""How often the aging job runs (in hours)."""

# ---------------------------------------------------------------------------
# Module-level scheduler instance
# ---------------------------------------------------------------------------

_scheduler: BackgroundScheduler | None = None


# ---------------------------------------------------------------------------
# Job function
# ---------------------------------------------------------------------------


def run_fit_profile_aging() -> None:
    """
    Execute one pass of the fit-profile aging logic:
    1. Create a new DB session.
    2. Compute cutoff = now() - 30 days.
    3. Call FitProfileRepository.mark_kept_bulk(db, cutoff).
    4. Log how many rows were updated.
    5. Close the session.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=AGING_DAYS)
        updated_count = FitProfileRepository.mark_kept_bulk(db, cutoff)
        if updated_count > 0:
            logger.info(
                "fit_profile_aging updated_rows=%d cutoff=%s",
                updated_count,
                cutoff.isoformat(),
            )
        else:
            logger.debug(
                "fit_profile_aging no_rows_to_update cutoff=%s",
                cutoff.isoformat(),
            )
    except Exception:
        logger.exception("fit_profile_aging job failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduler management
# ---------------------------------------------------------------------------


def start_aging_scheduler() -> BackgroundScheduler:
    """
    Create and start the APScheduler BackgroundScheduler with the
    FitProfileAgingJob registered on an IntervalTrigger (every 1 hour).

    Returns the scheduler instance so it can be shut down gracefully if needed.
    """
    global _scheduler  # noqa: PLW0603

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_fit_profile_aging,
        trigger=IntervalTrigger(hours=JOB_INTERVAL_HOURS),
        id="fit_profile_aging_job",
        name="Fit Profile Aging (pending → kept after 30 days)",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler

    logger.info(
        "fit_profile_aging_scheduler started interval_hours=%d aging_days=%d",
        JOB_INTERVAL_HOURS,
        AGING_DAYS,
    )
    return scheduler


def stop_aging_scheduler() -> None:
    """Shut down the aging scheduler gracefully if it is running."""
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("fit_profile_aging_scheduler stopped")
        _scheduler = None

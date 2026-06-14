"""Accept & pickup scheduling mock — in-memory job store."""

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from p2p.schemas import PickupJob

_jobs: dict[str, PickupJob] = {}


def schedule(sku_id: str) -> PickupJob:
    job = PickupJob(
        job_id=str(uuid.uuid4()),
        sku_id=sku_id,
        status="scheduled",
        pickup_eta="2-4 hours",
        agent=f"courier-{random.randint(100, 999)}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[PickupJob]:
    return _jobs.get(job_id)


def list_jobs() -> list[PickupJob]:
    return list(_jobs.values())

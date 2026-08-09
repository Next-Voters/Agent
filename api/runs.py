"""Background pipeline execution with in-flight status tracking only.

Runs are NOT stored locally — finished reports live in Supabase and are
served from there (see ``utils/report/reader.py``). This module keeps
only ephemeral per-region status: an entry exists while a run is queued
or running (used to deduplicate triggers and show progress), and a
failed entry sticks around until the region is run again so the portal
can surface the error. Successful runs are dropped from memory — the
saved report is the durable record.

The pipeline executes on a dedicated single-worker thread pool so that:

- runs are serialized (one pipeline at a time, avoiding LLM rate-limit
  contention), with queued runs waiting FIFO, and
- the chain always runs on a plain worker thread with no running event
  loop, which ``pipelines/node/run_agent_team.py`` requires because it
  calls ``asyncio.run()`` internally.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running")


@dataclass
class RunStatus:
    """Ephemeral status of the latest run for one region."""

    region: str
    status: str  # queued | running | failed
    created_at: str
    started_at: str | None = None
    error: str | None = None
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the status to a plain dict for JSON responses."""
        return asdict(self)


_STATUSES: dict[str, RunStatus] = {}
_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def run_statuses() -> list[RunStatus]:
    """Return current per-region run statuses (queued/running/failed)."""
    with _LOCK:
        return sorted(_STATUSES.values(), key=lambda s: s.created_at, reverse=True)


def region_is_active(region: str) -> bool:
    """Return True if the region already has a queued or running run."""
    with _LOCK:
        status = _STATUSES.get(region)
        return status is not None and status.status in ACTIVE_STATUSES


def start_run(region: str) -> RunStatus:
    """Register the region as queued and submit it to the executor."""
    status = RunStatus(region=region, status="queued", created_at=_utc_now())
    with _LOCK:
        _STATUSES[region] = status
    _EXECUTOR.submit(execute_run, region)
    return status


def execute_run(region: str) -> None:
    """Run the full pipeline for a region and save reports to Supabase.

    On success the region's status entry is removed (the saved report is
    the durable record); on failure the entry is marked ``failed`` with
    the error detail and kept until the region is run again.
    """
    from pipelines.nv_local import chain
    from utils.report.storage import save_report

    with _LOCK:
        status = _STATUSES.get(region)
    if status is None:
        logger.error(f"No status entry for region: {region}")
        return

    status.status = "running"
    status.started_at = _utc_now()
    logger.info(f"Running pipeline for region={region} (all topics)")

    try:
        result = chain.invoke({"region": region})
    except Exception as e:
        logger.error(f"Pipeline failed for {region}: {e}")
        status.status = "failed"
        status.error = str(e)
        return

    for topic, topic_data in result.get("topic_results", {}).items():
        label = f"{region} ({topic})"
        try:
            rid = save_report(region, topic, topic_data)
            if rid is None:
                logger.error(f"Failed to save report: {label}")
                status.failures.append(label)
            else:
                logger.info(f"Completed: {label} (report_id={rid})")
        except Exception as e:
            logger.error(f"Failed to save report: {label} — {e}")
            status.failures.append(label)

    if status.failures:
        logger.error(f"Pipeline failures: {status.failures}")
        status.status = "failed"
        return

    with _LOCK:
        _STATUSES.pop(region, None)

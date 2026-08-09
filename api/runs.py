"""In-memory pipeline run registry and background executor.

Runs are tracked in process memory only — history is lost on server
restart (finished reports still persist in Supabase). The pipeline
executes on a dedicated single-worker thread pool so that:

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
from uuid import uuid4

from utils.logger import get_logger

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running")


@dataclass
class Run:
    """A single pipeline run tracked in the in-memory registry."""

    id: str
    region: str
    status: str  # queued | running | succeeded | failed
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    failures: list[str] = field(default_factory=list)
    report_id: int | None = None
    result: dict[str, Any] | None = None

    def to_dict(self, include_result: bool = True) -> dict[str, Any]:
        """Serialize the run to a plain dict for JSON responses."""
        data = asdict(self)
        if not include_result:
            data.pop("result")
        return data


_RUNS: dict[str, Run] = {}
_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _utc_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def list_runs() -> list[Run]:
    """Return all registered runs, newest first."""
    with _LOCK:
        return sorted(_RUNS.values(), key=lambda r: r.created_at, reverse=True)


def get_run(run_id: str) -> Run | None:
    """Return the run with the given id, or None if unknown."""
    with _LOCK:
        return _RUNS.get(run_id)


def region_is_active(region: str) -> bool:
    """Return True if the region already has a queued or running run."""
    with _LOCK:
        return any(
            run.region == region and run.status in ACTIVE_STATUSES
            for run in _RUNS.values()
        )


def start_run(region: str) -> Run:
    """Register a new run for the region and submit it to the executor."""
    run = Run(
        id=uuid4().hex[:12],
        region=region,
        status="queued",
        created_at=_utc_now(),
    )
    with _LOCK:
        _RUNS[run.id] = run
    _EXECUTOR.submit(execute_run, run.id, region)
    return run


def execute_run(run_id: str, region: str) -> None:
    """Run the full pipeline for a region and record the outcome.

    Invokes the chain (all topics), saves each topic's report to
    Supabase, and updates the registry entry with status, failures,
    report id, and the serialized topic results.
    """
    from pipelines.nv_local import chain
    from utils.report.storage import save_report

    run = get_run(run_id)
    if run is None:
        logger.error(f"Unknown run id: {run_id}")
        return

    run.status = "running"
    run.started_at = _utc_now()
    logger.info(f"Running pipeline for region={region} (all topics)")

    try:
        result = chain.invoke({"region": region})
    except Exception as e:
        logger.error(f"Pipeline failed for {region}: {e}")
        run.status = "failed"
        run.error = str(e)
        run.finished_at = _utc_now()
        return

    topic_results = result.get("topic_results", {})
    for topic, topic_data in topic_results.items():
        label = f"{region} ({topic})"
        try:
            rid = save_report(region, topic, topic_data)
            if rid is None:
                logger.error(f"Failed to save report: {label}")
                run.failures.append(label)
            else:
                run.report_id = rid
                logger.info(f"Completed: {label} (report_id={rid})")
        except Exception as e:
            logger.error(f"Failed to save report: {label} — {e}")
            run.failures.append(label)

    run.result = _serialize_topic_results(topic_results)
    if run.failures:
        logger.error(f"Pipeline failures: {run.failures}")
        run.status = "failed"
    else:
        run.status = "succeeded"
    run.finished_at = _utc_now()


def _serialize_topic_results(topic_results: dict[str, Any]) -> dict[str, Any]:
    """Convert topic results into a JSON-serializable dict.

    ``legislation_summary`` may be a ``WriterOutput`` model or a plain
    dict depending on the caller; both are handled.
    """
    serialized: dict[str, Any] = {}
    for topic, topic_data in topic_results.items():
        summary = topic_data.get("legislation_summary")
        if summary is not None and hasattr(summary, "model_dump"):
            summary = summary.model_dump()
        serialized[topic] = {
            "topic_description": topic_data.get("topic_description", ""),
            "legislation_summary": summary,
            "legislation_sources": topic_data.get("legislation_sources", []),
        }
    return serialized

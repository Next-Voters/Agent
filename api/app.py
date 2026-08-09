"""FastAPI application: JSON API + built-in HTML portal.

Reports are served from Supabase (reports inner-joined with
report_headers); the server keeps no local run history — only ephemeral
in-flight status in ``api.runs``.

All routes are plain ``def`` (not ``async def``) so FastAPI executes
them in its threadpool — blocking Supabase calls never run on the event
loop, and the pipeline itself runs on the dedicated worker thread in
``api.runs``.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api import runs
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Next Voters Agent")

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


class RunRequest(BaseModel):
    """Request body for triggering a pipeline run."""

    region: str


def _fetch_supported_regions() -> dict[str, list[str]]:
    """Load supported regions grouped by type from Supabase, mapping failure to a 502."""
    from utils.supabase_client import get_supported_regions_from_db

    try:
        return get_supported_regions_from_db()
    except Exception as e:
        logger.error(f"Failed to get supported regions: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to load supported regions"
        ) from e


@app.get("/")
def index() -> FileResponse:
    """Serve the portal page (built Svelte app from frontend/)."""
    return FileResponse(_STATIC_DIR / "dist" / "index.html")


@app.get("/api/regions")
def get_regions() -> dict:
    """List supported regions grouped by type (e.g. country, city)."""
    return {"regions": _fetch_supported_regions()}


@app.post("/api/runs", status_code=202)
def create_run(request: RunRequest) -> dict:
    """Trigger a pipeline run for a region.

    Returns 400 for unknown regions and 409 if the region already has a
    queued or running run.
    """
    region = request.region
    supported_regions = _fetch_supported_regions()
    known_regions = {r for regions in supported_regions.values() for r in regions}
    if region not in known_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Region '{region}' not in supported regions",
        )
    if runs.region_is_active(region):
        raise HTTPException(
            status_code=409,
            detail=f"A run for region '{region}' is already queued or running",
        )
    return runs.start_run(region).to_dict()


@app.get("/api/runs")
def get_runs() -> dict:
    """Current per-region run statuses (queued/running/failed only)."""
    return {"runs": [status.to_dict() for status in runs.run_statuses()]}


@app.get("/api/reports")
def get_reports() -> dict:
    """List saved reports from Supabase, newest first."""
    from utils.report.reader import list_reports

    try:
        return {"reports": list_reports()}
    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        raise HTTPException(status_code=502, detail="Failed to load reports") from e


@app.get("/api/reports/{report_id}")
def get_report(report_id: int) -> dict:
    """Fetch one report with its headers grouped by topic."""
    from utils.report.reader import get_report as read_report

    try:
        report = read_report(report_id)
    except Exception as e:
        logger.error(f"Failed to load report {report_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to load report") from e
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown report id: {report_id}")
    return report


@app.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int) -> None:
    """Delete a saved report and its headers."""
    from utils.report.storage import delete_report as remove_report

    try:
        deleted = remove_report(report_id)
    except Exception as e:
        logger.error(f"Failed to delete report {report_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to delete report") from e
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unknown report id: {report_id}")

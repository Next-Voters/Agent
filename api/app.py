"""FastAPI application: JSON API + built-in HTML portal.

All routes are plain ``def`` (not ``async def``) so FastAPI executes
them in its threadpool — blocking Supabase calls never run on the event
loop, and the pipeline itself runs on the dedicated worker thread in
``api.runs``.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api import runs
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Next Voters Agent")

_STATIC_DIR = Path(__file__).parent / "static"


class RunRequest(BaseModel):
    """Request body for triggering a pipeline run."""

    region: str


def _fetch_supported_regions() -> list[str]:
    """Load supported regions from Supabase, mapping failure to a 502."""
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
    """Serve the portal page."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/api/regions")
def get_regions() -> dict:
    """List supported regions."""
    return {"regions": _fetch_supported_regions()}


@app.post("/api/runs", status_code=202)
def create_run(request: RunRequest) -> dict:
    """Trigger a pipeline run for a region.

    Returns 400 for unknown regions and 409 if the region already has a
    queued or running run.
    """
    region = request.region
    supported_regions = _fetch_supported_regions()
    if region not in supported_regions:
        raise HTTPException(
            status_code=400,
            detail=f"Region '{region}' not in supported regions",
        )
    if runs.region_is_active(region):
        raise HTTPException(
            status_code=409,
            detail=f"A run for region '{region}' is already queued or running",
        )
    run = runs.start_run(region)
    return run.to_dict(include_result=False)


@app.get("/api/runs")
def get_runs() -> dict:
    """List all runs (newest first), without result payloads."""
    return {"runs": [run.to_dict(include_result=False) for run in runs.list_runs()]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """Fetch a single run, including its result when finished."""
    run = runs.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run id: {run_id}")
    return run.to_dict()

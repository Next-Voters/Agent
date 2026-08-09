"""Integration tests for the FastAPI portal and the run executor.

All external I/O (Supabase, pipeline chain) is mocked so the tests
exercise the orchestration logic without network calls.

Patch targets use the source-module paths, NOT "api.runs.xyz", because
the pipeline dependencies are imported INSIDE execute_run (local
imports) and therefore never exist in the module-level namespace.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import runs
from api.app import app
from utils.schemas.pydantic import LegislationItem, WriterOutput

# ---------------------------------------------------------------------------
# Patch target constants — keeps the test bodies readable
# ---------------------------------------------------------------------------

_GET_REGIONS = "utils.supabase_client.get_supported_regions_from_db"
_CHAIN = "pipelines.nv_local.chain"
_SAVE_REPORT = "utils.report.storage.save_report"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry():
    """Reset the in-memory run registry between tests."""
    runs._RUNS.clear()
    yield
    runs._RUNS.clear()


def _writer_output_with_item():
    return WriterOutput(
        items=[LegislationItem(header="h", bullets=["b"], cited_sources=[])]
    )


def _chain_result(region="toronto", topics=("housing",)):
    """Build a synthetic chain.invoke() result."""
    return {
        "region": region,
        "topic_results": {
            t: {
                "topic_description": f"{t} policy",
                "legislation_sources": ["https://toronto.ca"],
                "legislation_content": ["content"],
                "notes": "notes",
                "legislation_summary": _writer_output_with_item(),
            }
            for t in topics
        },
    }


def _register_run(region="toronto"):
    """Register a run directly in the registry, bypassing the executor."""
    run = runs.Run(id="testrun", region=region, status="queued", created_at="t0")
    runs._RUNS[run.id] = run
    return run


# ---------------------------------------------------------------------------
# Executor: pipeline execution
# ---------------------------------------------------------------------------


class TestExecuteRun:
    def test_pipeline_failure_marks_run_failed(self):
        run = _register_run()
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT):
            mock_chain.invoke.side_effect = RuntimeError("agent loop exploded")
            runs.execute_run(run.id, run.region)

        assert run.status == "failed"
        assert "agent loop exploded" in run.error
        assert run.finished_at is not None
        assert run.result is None

    def test_successful_run_marks_run_succeeded(self):
        run = _register_run()
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT, return_value=42):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run(run.id, run.region)

        assert run.status == "succeeded"
        assert run.report_id == 42
        assert run.failures == []
        assert run.error is None
        assert run.finished_at is not None

    def test_result_is_serialized(self):
        run = _register_run()
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT, return_value=42):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run(run.id, run.region)

        summary = run.result["housing"]["legislation_summary"]
        assert isinstance(summary, dict)
        assert summary["items"][0]["header"] == "h"
        assert run.result["housing"]["legislation_sources"] == ["https://toronto.ca"]

    def test_save_report_called_per_topic(self):
        run = _register_run()
        with (
            patch(_CHAIN) as mock_chain,
            patch(_SAVE_REPORT, return_value=10) as mock_save,
        ):
            mock_chain.invoke.return_value = _chain_result(
                topics=("housing", "transit")
            )
            runs.execute_run(run.id, run.region)

        assert mock_save.call_count == 2
        called_topics = {c.args[1] for c in mock_save.call_args_list}
        assert called_topics == {"housing", "transit"}

    def test_save_report_returns_none_is_treated_as_failure(self):
        run = _register_run()
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT, return_value=None):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run(run.id, run.region)

        assert run.status == "failed"
        assert run.failures == ["toronto (housing)"]
        assert run.report_id is None

    def test_save_report_exception_treated_as_failure(self):
        run = _register_run()
        with (
            patch(_CHAIN) as mock_chain,
            patch(_SAVE_REPORT, side_effect=Exception("write failed")),
        ):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run(run.id, run.region)

        assert run.status == "failed"
        assert run.failures == ["toronto (housing)"]


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


client = TestClient(app)


class TestRegionsEndpoint:
    def test_returns_regions(self):
        with patch(_GET_REGIONS, return_value=["ottawa", "toronto"]):
            res = client.get("/api/regions")
        assert res.status_code == 200
        assert res.json() == {"regions": ["ottawa", "toronto"]}

    def test_supabase_error_returns_502(self):
        with patch(_GET_REGIONS, side_effect=Exception("DB down")):
            res = client.get("/api/regions")
        assert res.status_code == 502


class TestCreateRunEndpoint:
    def test_valid_region_returns_202(self):
        with (
            patch(_GET_REGIONS, return_value=["toronto"]),
            patch.object(runs._EXECUTOR, "submit") as mock_submit,
        ):
            res = client.post("/api/runs", json={"region": "toronto"})

        assert res.status_code == 202
        body = res.json()
        assert body["region"] == "toronto"
        assert body["status"] == "queued"
        assert "result" not in body
        mock_submit.assert_called_once()

    def test_unknown_region_returns_400(self):
        with patch(_GET_REGIONS, return_value=["toronto"]):
            res = client.post("/api/runs", json={"region": "nonexistent-city"})
        assert res.status_code == 400

    def test_supabase_error_returns_502(self):
        with patch(_GET_REGIONS, side_effect=Exception("DB down")):
            res = client.post("/api/runs", json={"region": "toronto"})
        assert res.status_code == 502

    def test_duplicate_active_region_returns_409(self):
        _register_run("toronto")
        with patch(_GET_REGIONS, return_value=["toronto"]):
            res = client.post("/api/runs", json={"region": "toronto"})
        assert res.status_code == 409

    def test_finished_region_can_run_again(self):
        run = _register_run("toronto")
        run.status = "succeeded"
        with (
            patch(_GET_REGIONS, return_value=["toronto"]),
            patch.object(runs._EXECUTOR, "submit"),
        ):
            res = client.post("/api/runs", json={"region": "toronto"})
        assert res.status_code == 202


class TestRunEndpoints:
    def test_list_runs_excludes_result(self):
        run = _register_run()
        run.result = {"housing": {}}
        res = client.get("/api/runs")
        assert res.status_code == 200
        body = res.json()
        assert len(body["runs"]) == 1
        assert body["runs"][0]["id"] == run.id
        assert "result" not in body["runs"][0]

    def test_get_run_includes_result(self):
        run = _register_run()
        run.result = {"housing": {}}
        res = client.get(f"/api/runs/{run.id}")
        assert res.status_code == 200
        assert res.json()["result"] == {"housing": {}}

    def test_unknown_run_returns_404(self):
        res = client.get("/api/runs/nope")
        assert res.status_code == 404


class TestIndexEndpoint:
    def test_serves_portal_page(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Next Voters Agent" in res.text

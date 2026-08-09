"""Integration tests for the FastAPI portal and the run executor.

All external I/O (Supabase, pipeline chain) is mocked so the tests
exercise the orchestration logic without network calls.

Patch targets use the source-module paths, NOT "api.runs.xyz" or
"api.app.xyz", because the pipeline and report-reader dependencies are
imported INSIDE the functions (local imports) and therefore never exist
in the module-level namespaces.
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
_LIST_REPORTS = "utils.report.reader.list_reports"
_GET_REPORT = "utils.report.reader.get_report"
_DELETE_REPORT = "utils.report.storage.delete_report"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_statuses():
    """Reset the in-memory status map between tests."""
    runs._STATUSES.clear()
    yield
    runs._STATUSES.clear()


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


def _register_status(region="toronto", status="queued"):
    """Register a status entry directly, bypassing the executor."""
    entry = runs.RunStatus(region=region, status=status, created_at="t0")
    runs._STATUSES[region] = entry
    return entry


# ---------------------------------------------------------------------------
# Executor: pipeline execution
# ---------------------------------------------------------------------------


class TestExecuteRun:
    def test_successful_run_removes_status_entry(self):
        _register_status("toronto")
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT, return_value=42):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run("toronto")

        assert "toronto" not in runs._STATUSES

    def test_pipeline_failure_marks_status_failed(self):
        entry = _register_status("toronto")
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT):
            mock_chain.invoke.side_effect = RuntimeError("agent loop exploded")
            runs.execute_run("toronto")

        assert entry.status == "failed"
        assert "agent loop exploded" in entry.error
        assert runs._STATUSES["toronto"] is entry

    def test_save_report_called_per_topic(self):
        _register_status("toronto")
        with (
            patch(_CHAIN) as mock_chain,
            patch(_SAVE_REPORT, return_value=10) as mock_save,
        ):
            mock_chain.invoke.return_value = _chain_result(
                topics=("housing", "transit")
            )
            runs.execute_run("toronto")

        assert mock_save.call_count == 2
        called_topics = {c.args[1] for c in mock_save.call_args_list}
        assert called_topics == {"housing", "transit"}

    def test_save_report_returns_none_is_treated_as_failure(self):
        entry = _register_status("toronto")
        with patch(_CHAIN) as mock_chain, patch(_SAVE_REPORT, return_value=None):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run("toronto")

        assert entry.status == "failed"
        assert entry.failures == ["toronto (housing)"]

    def test_save_report_exception_treated_as_failure(self):
        entry = _register_status("toronto")
        with (
            patch(_CHAIN) as mock_chain,
            patch(_SAVE_REPORT, side_effect=Exception("write failed")),
        ):
            mock_chain.invoke.return_value = _chain_result()
            runs.execute_run("toronto")

        assert entry.status == "failed"
        assert entry.failures == ["toronto (housing)"]


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
        _register_status("toronto", status="running")
        with patch(_GET_REGIONS, return_value=["toronto"]):
            res = client.post("/api/runs", json={"region": "toronto"})
        assert res.status_code == 409

    def test_failed_region_can_run_again(self):
        _register_status("toronto", status="failed")
        with (
            patch(_GET_REGIONS, return_value=["toronto"]),
            patch.object(runs._EXECUTOR, "submit"),
        ):
            res = client.post("/api/runs", json={"region": "toronto"})
        assert res.status_code == 202


class TestRunStatusEndpoint:
    def test_lists_current_statuses(self):
        _register_status("toronto", status="running")
        res = client.get("/api/runs")
        assert res.status_code == 200
        body = res.json()
        assert len(body["runs"]) == 1
        assert body["runs"][0]["region"] == "toronto"
        assert body["runs"][0]["status"] == "running"

    def test_empty_when_no_runs(self):
        res = client.get("/api/runs")
        assert res.json() == {"runs": []}


class TestReportsEndpoints:
    def test_lists_reports(self):
        reports = [
            {"id": 48, "region": "Toronto", "report_date": "2026-08-09"},
            {"id": 45, "region": "San Francisco", "report_date": "2026-06-02"},
        ]
        with patch(_LIST_REPORTS, return_value=reports):
            res = client.get("/api/reports")
        assert res.status_code == 200
        assert res.json() == {"reports": reports}

    def test_list_supabase_error_returns_502(self):
        with patch(_LIST_REPORTS, side_effect=Exception("DB down")):
            res = client.get("/api/reports")
        assert res.status_code == 502

    def test_get_report_detail(self):
        report = {
            "id": 48,
            "region": "Toronto",
            "report_date": "2026-08-09",
            "topics": {
                "civil rights": [
                    {"header": "h", "bullets": ["b"], "sources": ["https://x.ca"]}
                ]
            },
        }
        with patch(_GET_REPORT, return_value=report) as mock_get:
            res = client.get("/api/reports/48")
        assert res.status_code == 200
        assert res.json() == report
        mock_get.assert_called_once_with(48)

    def test_unknown_report_returns_404(self):
        with patch(_GET_REPORT, return_value=None):
            res = client.get("/api/reports/999")
        assert res.status_code == 404

    def test_detail_supabase_error_returns_502(self):
        with patch(_GET_REPORT, side_effect=Exception("DB down")):
            res = client.get("/api/reports/48")
        assert res.status_code == 502

    def test_delete_report(self):
        with patch(_DELETE_REPORT, return_value=True) as mock_delete:
            res = client.delete("/api/reports/48")
        assert res.status_code == 204
        mock_delete.assert_called_once_with(48)

    def test_delete_unknown_report_returns_404(self):
        with patch(_DELETE_REPORT, return_value=False):
            res = client.delete("/api/reports/999")
        assert res.status_code == 404

    def test_delete_supabase_error_returns_502(self):
        with patch(_DELETE_REPORT, side_effect=Exception("DB down")):
            res = client.delete("/api/reports/48")
        assert res.status_code == 502


class TestIndexEndpoint:
    def test_serves_portal_page(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Next Voters Agent" in res.text

    def test_serves_built_frontend_bundle(self):
        """The JS bundle referenced by the built page must be served."""
        import re

        page = client.get("/").text
        match = re.search(r'src="(/static/dist/assets/[^"]+\.js)"', page)
        assert match, (
            "built page references no JS bundle — run `npm run build` in frontend/"
        )
        res = client.get(match.group(1))
        assert res.status_code == 200
        assert "javascript" in res.headers["content-type"]

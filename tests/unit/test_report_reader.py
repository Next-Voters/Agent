"""Unit tests for utils/report/reader.py."""

from unittest.mock import MagicMock, patch

from utils.report.reader import get_report, list_reports


def _client_returning(data):
    """Build a mock Supabase client whose query chain returns ``data``."""
    client = MagicMock()
    client.table.return_value.select.return_value.order.return_value.order.return_value.execute.return_value.data = data
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = data
    return client


class TestListReports:
    def test_returns_rows(self):
        rows = [{"id": 48, "region": "Toronto", "report_date": "2026-08-09"}]
        with patch(
            "utils.report.reader.get_supabase_client",
            return_value=_client_returning(rows),
        ):
            assert list_reports() == rows

    def test_empty_data_returns_empty_list(self):
        with patch(
            "utils.report.reader.get_supabase_client",
            return_value=_client_returning(None),
        ):
            assert list_reports() == []


class TestGetReport:
    def test_missing_report_returns_none(self):
        with patch(
            "utils.report.reader.get_supabase_client",
            return_value=_client_returning([]),
        ):
            assert get_report(999) is None

    def test_groups_headers_by_topic_and_strips_markers(self):
        rows = [
            {
                "id": 48,
                "region": "Toronto",
                "report_date": "2026-08-09",
                "report_headers": [
                    {
                        "topic_id": 2,
                        "header": "Plan endorsed[1]",
                        "bullets": ["The Board endorsed the plan in 2016.[2]"],
                        "sources": ["https://tpsb.ca/agenda.pdf"],
                        "supported_topics": {"topic_name": "civil rights"},
                    },
                    {
                        "topic_id": 3,
                        "header": "Vacancy tax passes",
                        "bullets": ["Council approved the tax."],
                        "sources": [],
                        "supported_topics": {"topic_name": "housing"},
                    },
                ],
            }
        ]
        with patch(
            "utils.report.reader.get_supabase_client",
            return_value=_client_returning(rows),
        ):
            report = get_report(48)

        assert report["id"] == 48
        assert list(report["topics"]) == ["civil rights", "housing"]
        item = report["topics"]["civil rights"][0]
        assert item["header"] == "Plan endorsed"
        assert item["bullets"] == ["The Board endorsed the plan in 2016."]

    def test_missing_topic_name_falls_back_to_topic_id(self):
        rows = [
            {
                "id": 1,
                "region": "Toronto",
                "report_date": "2026-08-09",
                "report_headers": [
                    {
                        "topic_id": 7,
                        "header": "h",
                        "bullets": ["b"],
                        "sources": [],
                        "supported_topics": None,
                    }
                ],
            }
        ]
        with patch(
            "utils.report.reader.get_supabase_client",
            return_value=_client_returning(rows),
        ):
            report = get_report(1)

        assert list(report["topics"]) == ["topic 7"]

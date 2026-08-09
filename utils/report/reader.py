"""Read saved reports from the Supabase reports and report_headers tables."""

from typing import Any

from utils.schemas.pydantic import strip_citation_markers
from utils.supabase_client import get_supabase_client


def list_reports() -> list[dict[str, Any]]:
    """List saved reports, newest first.

    Returns:
        List of dicts with ``id``, ``region``, and ``report_date``.

    Raises:
        Exception: If Supabase is unreachable or the query fails.
    """
    response = (
        get_supabase_client()
        .table("reports")
        .select("id, region, report_date")
        .order("report_date", desc=True)
        .order("id", desc=True)
        .execute()
    )
    return response.data or []


def get_report(report_id: int) -> dict[str, Any] | None:
    """Fetch one report with its headers, inner-joined and grouped by topic.

    Legacy rows may contain inline citation markers in header/bullet text;
    they are stripped on read so the portal always renders clean prose.

    Args:
        report_id: The reports table primary key.

    Returns:
        Dict with ``id``, ``region``, ``report_date``, and ``topics`` —
        a mapping of topic name to its list of items (header, bullets,
        sources) — or None if the report does not exist.

    Raises:
        Exception: If Supabase is unreachable or the query fails.
    """
    response = (
        get_supabase_client()
        .table("reports")
        .select(
            "id, region, report_date, "
            "report_headers!inner(topic_id, header, bullets, sources, "
            "supported_topics(topic_name))"
        )
        .eq("id", report_id)
        .execute()
    )
    if not response.data:
        return None

    report = response.data[0]
    topics: dict[str, list[dict[str, Any]]] = {}
    for row in report.get("report_headers", []):
        topic_info = row.get("supported_topics") or {}
        topic_name = topic_info.get("topic_name") or f"topic {row.get('topic_id')}"
        topics.setdefault(topic_name, []).append(
            {
                "header": strip_citation_markers(row.get("header") or ""),
                "bullets": [
                    strip_citation_markers(b) for b in (row.get("bullets") or [])
                ],
                "sources": row.get("sources") or [],
            }
        )

    return {
        "id": report["id"],
        "region": report["region"],
        "report_date": report["report_date"],
        "topics": dict(sorted(topics.items())),
    }

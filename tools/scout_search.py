"""Scout search tool — shallow recency search for subtopic discovery.

Returns headlines and snippets only (no page extraction, no compression),
so the lead researcher can ground its subtopic selection in what is
actually happening right now without doing deep research itself.
"""

from typing import Annotated

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt.tool_node import InjectedState
from langgraph.types import Command

from tools._helpers import err, ok
from tools.services.tavily import _EXCLUDE_DOMAINS, tavily_search
from utils.logger import get_logger

logger = get_logger(__name__)

_SCOUT_MAX_RESULTS = 5


@tool
def scout_search(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    region: Annotated[str, InjectedState("region")],
) -> Command:
    """Scan recent headlines and snippets to discover timely subtopics.

    Lightweight search over the last week, scoped to the region. Returns
    titles, URLs, and short snippets ONLY — no page content. Use it to
    find out what is currently happening for your topic before dispatching
    researchers; do NOT use it for deep research (delegate that to
    researcher_agent_tool).

    Args:
        query: Short query for recent activity, e.g.
            "city council housing agenda" or "police oversight news".
    """
    try:
        raw = tavily_search(
            query=f'{query} "{region}"',
            max_results=_SCOUT_MAX_RESULTS,
            search_depth="basic",
            time_range="week",
            exclude_domains=_EXCLUDE_DOMAINS,
        )
    except Exception as e:
        logger.error(f"Scout search failed for query={query!r}: {e}")
        return err(tool_call_id, f"Scout search failed: {e}")

    results = raw.get("results", [])
    if not results:
        return ok(
            tool_call_id,
            f"No recent results for '{query}' in {region}. "
            "Try a different angle or fall back to general knowledge.",
        )

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        url = r.get("url", "").strip()
        snippet = r.get("content", "").strip()[:300]
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}")

    return ok(tool_call_id, "\n".join(lines))

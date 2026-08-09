"""Unit tests for utils/schemas/pydantic.py output validators."""

from config.constants import MAX_ITEMS_PER_TOPIC
from utils.schemas.pydantic import (
    LegislationItem,
    WriterOutput,
    strip_citation_markers,
)


class TestStripCitationMarkers:
    def test_marker_after_period(self):
        text = "The Board endorsed the interim modernization plan in 2016.[2]"
        assert (
            strip_citation_markers(text)
            == "The Board endorsed the interim modernization plan in 2016."
        )

    def test_chained_markers(self):
        assert strip_citation_markers("The fund grew to $5M.[2][3]") == (
            "The fund grew to $5M."
        )

    def test_range_and_list_markers(self):
        assert strip_citation_markers("Council voted 7-2.[1-3]") == "Council voted 7-2."
        assert strip_citation_markers("Council voted 7-2.[1, 2]") == (
            "Council voted 7-2."
        )

    def test_mid_sentence_marker(self):
        assert strip_citation_markers("The plan [2] was endorsed.") == (
            "The plan was endorsed."
        )

    def test_clean_text_unchanged(self):
        text = "Council passed the budget 7-2."
        assert strip_citation_markers(text) == text

    def test_non_citation_brackets_preserved(self):
        text = "Measure [B] passed with 60% support."
        assert strip_citation_markers(text) == text


class TestLegislationItemValidation:
    def test_bullets_are_stripped_on_construction(self):
        item = LegislationItem(
            header="Police board endorses modernization plan",
            bullets=[
                "The Board endorsed the interim modernization plan in 2016.[2]",
                "The plan covers oversight, contracts, and discipline.[2][4]",
            ],
            cited_sources=[2, 4],
        )
        assert item.bullets == [
            "The Board endorsed the interim modernization plan in 2016.",
            "The plan covers oversight, contracts, and discipline.",
        ]

    def test_header_is_stripped_on_construction(self):
        item = LegislationItem(header="Plan endorsed[1]", bullets=["b"])
        assert item.header == "Plan endorsed"

    def test_cited_sources_untouched(self):
        item = LegislationItem(header="h", bullets=["b.[1]"], cited_sources=[1])
        assert item.cited_sources == [1]


class TestWriterOutputItemCap:
    def _items(self, n):
        return [LegislationItem(header=f"item {i}", bullets=["b"]) for i in range(n)]

    def test_excess_items_truncated_keeping_first(self):
        output = WriterOutput(items=self._items(MAX_ITEMS_PER_TOPIC + 3))
        assert len(output.items) == MAX_ITEMS_PER_TOPIC
        assert output.items[0].header == "item 0"
        assert output.items[-1].header == f"item {MAX_ITEMS_PER_TOPIC - 1}"

    def test_at_cap_unchanged(self):
        output = WriterOutput(items=self._items(MAX_ITEMS_PER_TOPIC))
        assert len(output.items) == MAX_ITEMS_PER_TOPIC

    def test_under_cap_unchanged(self):
        output = WriterOutput(items=self._items(1))
        assert len(output.items) == 1

    def test_empty_unchanged(self):
        assert WriterOutput(items=[]).items == []

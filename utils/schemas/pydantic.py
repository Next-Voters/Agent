"""Shared Pydantic models used to structure LLM responses."""

import re

from pydantic import BaseModel, Field, field_validator

# Inline citation markers like [2], [1][3], [1-3], or [1, 2] — the writer
# prompt forbids them, but the model occasionally emits them anyway.
_CITATION_MARKERS = re.compile(r"\s*\[\d+(?:\s*[-–,]\s*\d+)*\]")


def strip_citation_markers(text: str) -> str:
    """Remove inline bracketed citation markers from display text.

    Attribution lives in the structured ``cited_sources`` field; markers
    like ``[2]`` must never reach report headers or bullets.
    """
    cleaned = _CITATION_MARKERS.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


class ReflectionEntry(BaseModel):
    """Structured reflection produced by the reflection tool."""

    reflection: str | None = Field(
        default=None,
        description="Based on the current conversation that you have had, build a complete, but succinct reflection to create enriched context for agent",
    )
    gaps_identified: list[str] = Field(
        default_factory=list,
        description="Information gaps or missing context that needs to be addressed",
    )
    next_action: str | None = Field(
        default=None,
        description="Specific action planned for the next iteration (e.g., search query, tool to use)",
    )


class LegislationItem(BaseModel):
    """A single legislation action with headline and bullet points."""

    header: str = Field(
        description="Short factual headline, e.g. 'Council passes good cause eviction package'"
    )
    bullets: list[str] = Field(
        description="List of cited bullet points explaining what happened"
    )
    cited_sources: list[int] = Field(
        default_factory=list,
        description="List of source numbers (from the SOURCES list) cited by this item's bullets",
    )

    @field_validator("header", mode="after")
    @classmethod
    def _strip_header_markers(cls, value: str) -> str:
        """Enforce marker-free headers regardless of what the LLM emits."""
        return strip_citation_markers(value)

    @field_validator("bullets", mode="after")
    @classmethod
    def _strip_bullet_markers(cls, value: list[str]) -> list[str]:
        """Enforce marker-free bullets regardless of what the LLM emits."""
        return [strip_citation_markers(bullet) for bullet in value]


class WriterOutput(BaseModel):
    """Structured output: list of legislation items discovered for a topic."""

    items: list[LegislationItem] = Field(
        default_factory=list,
        description="List of legislation items found for this topic",
    )

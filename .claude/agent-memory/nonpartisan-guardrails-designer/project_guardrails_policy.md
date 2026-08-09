---
name: guardrails-policy
description: Project policy that modified system prompts get a nonpartisan guardrails pass, plus the canonical in-repo pattern and the governing bias principle
metadata:
  type: project
---

System prompts in `config/system_prompts/` are expected to carry a nonpartisan guardrails
section, and modified prompts get a guardrails pass before they ship.

**Why:** The product summarizes municipal legislation for a general, politically mixed
subscriber audience. Per `docs/AGENTIC_ARCHITECTURE.md`, "political neutrality is core
product — the moment briefs read as partisan, a large part of the market will not touch it."

**How to apply:**
- The canonical house pattern lives in `config/system_prompts/legislation_finder.py`
  ("Nonpartisan Impact Screening Guardrails (Mandatory)"): a `**Principle:**` line, numbered
  binding rules with bold lead-ins, then a one-line echo in the prompt's Hard Constraints.
  Read it before writing a new guardrails block so the new one matches.
- Governing philosophy is `docs/AGENTIC_ARCHITECTURE.md` core principle #6: "The bias engine
  is retrieval and display discipline, not neutralized language. Surface competing framings
  with attribution. Do not launder contested claims into fake-neutral prose." So guardrails
  should require attributing contested claims to a named holder — not deleting the
  disagreement or flattening it into fake-neutral phrasing.
- Prompts are single string constants. Agent prompts are substituted with `str.format()`
  (`agents/researcher_agent.py`, `agents/lead_researcher_agent.py`); node prompts use chained
  `str.replace()` on named placeholders (`pipelines/node/summary_writer.py`, `note_taker.py`).
  Either way, guardrails text must contain no `{` or `}` beyond the prompt's real placeholders.
- Language-side guardrails do not cover selection. Most guardrail blocks constrain *how* an
  item is written (merit language, verbs, attribution). Any prompt surface that *ranks, caps,
  folds, or drops* items is a separate bias vector and needs its own rule: party-blind
  ranking, ties broken on impact rather than newsworthiness, and a check that the kept set
  does not skew to one political side.

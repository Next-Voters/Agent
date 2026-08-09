# Architecture

**Next Voters Agent** is a multi-agent AI research pipeline that discovers, researches, and summarizes municipal legislation across cities, exposed through a small web portal. This document is the map; each subsystem has its own deep-dive below.

At a glance, a run looks like:

```
Browser (portal at /) → FastAPI server (api/)
  → run queued in the in-memory registry → executed on a background worker thread
  → LangGraph agent team researches legislation (all topics for the region)
  → writes report to Supabase → portal polls status and renders the results
```

For the highest-level project overview and conventions, see the repository [`CLAUDE.md`](../CLAUDE.md).

## System design

- [Agentic Architecture](AGENTIC_ARCHITECTURE.md) — how the pipeline reads legislation like an analyst: the problem, the load-bearing design principles, and the LangGraph agents, nodes, and tools that produce cited briefs.

## Infrastructure

- [Database Infrastructure](DB_INFRASTRUCTURE.md) — the Supabase schema: pipeline tables (region/topic config, subscribers, reports), platform tables, LangGraph persistence, and RLS.

## Operations

- [Operations](OPERATIONS.md) — how the system is run in development and in a container, plus configuration and secrets handling.

## Subsystems & deep dives

- [Context Compression — overview](compact_prompt/GENERAL.md) — the CompactPrompt token-pruning approach used to compress fetched page content before it enters an agent's context window.
- [Self-Information Scoring Mechanism](compact_prompt/SELF_INFORMATION_MECHANISM.md) — the scoring internals behind the compressor.
- [CompactPrompt Engineering Session Log](compactprompt-session.md) — the engineering session that built the token-pruning compressor.

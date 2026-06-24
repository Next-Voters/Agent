# Architecture

**Next Voters Agent** is a multi-agent AI research pipeline that discovers, researches, and summarizes municipal legislation across cities, then delivers topic-specific, cited briefs to subscribers. This document is the map; each subsystem has its own deep-dive below.

At a glance, a weekly run looks like:

```
EventBridge → Dispatcher Lambda → ECS Fargate task (per region)
  → LangGraph agent team researches legislation → writes report to Supabase
  → enqueues {region, report_id} to SQS
      → Email Lambda  (sends the brief via Mailgun)
      → Worker Lambda (post-processes the saved report)
```

For the highest-level project overview and conventions, see the repository [`CLAUDE.md`](../CLAUDE.md).

## System design

- [Agentic Architecture](AGENTIC_ARCHITECTURE.md) — how the pipeline reads legislation like an analyst: the problem, the load-bearing design principles, and the LangGraph agents, nodes, and tools that produce cited briefs.

## Infrastructure

- [AWS Architecture](AWS_ARCHITECTURE.md) — the runtime deployment (EventBridge, Dispatcher/Email/Worker Lambdas, ECS Fargate, SQS queues + DLQs) and the CI/CD image-management flow across ECR repositories.
- [Database Infrastructure](DB_INFRASTRUCTURE.md) — the Supabase schema: pipeline tables (region/topic config, subscribers, reports), platform tables, LangGraph persistence, and RLS.

## Operations

- [Operations](OPERATIONS.md) — how the system is run in development and deployed in production-like environments, plus configuration and secrets handling.
- [Email Lambda: SES → Mailgun + SSM Migration](EMAIL_LAMBDA_MAILGUN_MIGRATION.md) — handoff prompt and reference implementation for migrating the (separate-repo) Email Lambda off SES to Mailgun, with secrets fetched from SSM.

## Subsystems & deep dives

- [Context Compression — overview](compact_prompt/GENERAL.md) — the CompactPrompt token-pruning approach used to compress fetched page content before it enters an agent's context window.
- [Self-Information Scoring Mechanism](compact_prompt/SELF_INFORMATION_MECHANISM.md) — the scoring internals behind the compressor.
- [CompactPrompt Engineering Session Log](compactprompt-session.md) — the engineering session that built the token-pruning compressor.

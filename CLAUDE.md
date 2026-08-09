# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Next Voters Agent** is a multi-agent AI research pipeline that discovers, researches, and summarizes municipal legislation across cities. It makes government information accessible to communities that lack time or resources to track local officials.

The system runs as a FastAPI web server (locally or in Docker) with a built-in HTML portal. Users trigger pipeline runs per region on demand; each run researches legislation for that region across all topics, orchestrated by LangGraph-based agents, and stores structured results (headers + bullets) in Supabase.

## Development Setup

### Environment

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

- Copy `.env.example` to `.env` and set required keys
- All entrypoints and modules that read env vars call `load_dotenv()` from `python-dotenv`, so `.env` is loaded automatically
- **Entrypoint**: `main.py` starts the FastAPI server (`api/app.py`) via uvicorn on `HOST`/`PORT` (defaults `0.0.0.0:8000`). Pipeline runs are triggered through the portal at `/` or the JSON API.

### Common Commands

```bash
# Compile check (catches syntax errors early)
python -m compileall -q .

# Run the test suite
pytest tests

# Start the web server (portal at http://localhost:8000).
# Requires OPENAI_API_KEY + TAVILY_API_KEY + SUPABASE_URL/KEY.
python main.py

# Dev mode with auto-reload
uvicorn api.app:app --reload
```

**Post-implementation verification**: After any code changes, always run `python -m compileall -q .` followed by `pytest tests` to confirm both compile-time and behavioral correctness. For entrypoint/API changes, also start `python main.py` and exercise the affected endpoints.

### Testing

- `pytest tests` — unit tests plus integration tests for the API and run executor (`tests/integration/test_api.py`, all external I/O mocked)
- `python -m compileall -q .` to catch syntax errors
- Manual pipeline runs via the portal with test regions to verify data flow

## Architecture Overview

### Web Server + Run Execution

The FastAPI app (`api/app.py`) serves a single-page portal (`api/static/index.html`) and a JSON API:

| Method/Path | Behavior |
|---|---|
| `GET /` | Portal page (region picker, run status strip, per-city report sections; polls every 5s) |
| `GET /static/*` | Static assets (built Svelte bundle under `static/dist/`) |
| `GET /api/regions` | Supported regions from Supabase; 502 if Supabase unreachable |
| `POST /api/runs` `{"region": ...}` | Start a run — 202 accepted, 400 unknown region, 409 region already queued/running |
| `GET /api/runs` | Ephemeral per-region statuses (`queued | running | failed`) — no history, no results |
| `GET /api/reports` | Saved reports from the Supabase `reports` table, newest first |
| `GET /api/reports/{id}` | One report with `report_headers` inner-joined, grouped by topic name |

**Runs are NOT stored locally.** `api/runs.py` keeps only ephemeral per-region status: an entry exists while a run is queued/running (dedupe + progress), a failed entry persists until the region is re-run (so the portal can show the error), and successful runs are dropped — the saved report in Supabase is the durable record, served via `utils/report/reader.py`.

**Critical constraint**: `pipelines/node/run_agent_team.py` calls `asyncio.run(...)` inside a sync `RunnableLambda`, which crashes if invoked from a thread with a running event loop. Therefore:
- All FastAPI routes are plain `def` (executed in the threadpool), never `async def`
- The pipeline executes on a dedicated `ThreadPoolExecutor(max_workers=1)` — runs are serialized (one pipeline at a time, avoiding LLM rate-limit contention) and queued FIFO
- Do not "optimize" to `async def` routes + `await chain.ainvoke()`

### Pipeline Structure

The pipeline is a **fixed, deterministic sequence** of nodes composed via LangGraph. This makes the execution path predictable and operational.

```
run_agent_team → note_taker → summary_writer
```

**Key design**: Each node is a thin `RunnableSequence` that transforms pipeline state (`ChainData` TypedDict).

### Core Components

**Web/API** (`api/`):
- `app.py`: FastAPI app + routes (all sync `def`)
- `runs.py`: Background executor + ephemeral in-flight status map; `execute_run()` invokes the chain and saves per-topic reports to Supabase (no local result storage)
- `static/dist/`: Built Svelte portal (committed output of `frontend/`; do not edit by hand)

**Frontend** (`frontend/` — Svelte 5 + Vite):
- `src/App.svelte`: Root component — all UI state (regions, run statuses, reports, active report) via runes; groups reports into one section per city (`regionSections` derived state); polls the API every 5s
- `src/lib/StatusStrip.svelte`, `src/lib/RegionSection.svelte`, `src/lib/ReportDetail.svelte`: Presentational components; report detail expands inline on click within its city section
- `npm run build` (in `frontend/`) compiles into `api/static/dist/` — **the built output is committed**, so the Python server and Docker image never need Node. Rebuild and commit `api/static/dist` whenever `frontend/` changes.
- `npm run dev` runs the Vite dev server with `/api` proxied to `localhost:8000`

**Agents** (`agents/`):
- `researcher_agent.py`: ReAct subagent for issue-level legislation discovery, built with `create_agent` from `langchain.agents`. Terminates via `handoff` tool which writes summary to state and exits the graph.
- `lead_researcher_agent.py`: Supervisor agent that scouts the day's activity via `scout_search`, hands off timely subtopics to researchers, validates sources, and synthesizes findings

**Pipeline Nodes** (`pipelines/node/`):
- `run_agent_team.py`: Orchestrates lead researcher agents per topic, collects sources with compressed content, populates `legislation_content`
- `note_taker.py`: Compresses raw content into dense notes (single LLM call)
- `summary_writer.py`: Structured extraction of key legislative details (schema: `WriterOutput`)

**Utilities** (`utils/`):
- `llm/`: LLM factory (`get_llm()`, `get_structured_llm()`) with default config (gpt-5, temp=0, max_tokens=16384)
- `schemas/`:
  - `state.py`: `ChainData` TypedDict (pipeline state contract)
  - `pydantic.py`: Structured output schemas (e.g., `WriterOutput`)
- `report/`:
  - `storage.py`: Saves pipeline output to Supabase via a two-table upsert: parent `reports` row (per region+date) and child `report_headers` rows (per legislation item with topic, header, and bullets). Returns the `report_id` on success. Single function: `save_report(region, topic_name, result) → int | None`
  - `reader.py`: Serves saved reports back to the portal — `list_reports()` and `get_report(id)` (reports inner-joined with `report_headers`, grouped by topic name, legacy citation markers stripped on read)
- `content/`: Content processing and evaluation utilities
  - `compressor.py`: Context compression via `compress_text(text, rate, query)`. Uses blended self-information token pruning with head-truncation fallback. Called by `web_search` to compress extracted page content inline. Short content (<`MIN_CHARS_TO_COMPRESS` chars) bypasses compression.
  - `source_reliability.py`: Domain-level source reliability scoring and filtering — classifies URLs into government, legislative, news, other, or blocked tiers.
- `supabase_client.py`: Loads supported regions and topics from Supabase

**Tools** (`tools/` — root level):
- `web_search.py`: Web search + content retrieval tool — searches via Tavily, fetches full page content via Tavily Extract, compresses via static self-information scoring, returns compressed content to the researcher agent
- `scout_search.py`: Shallow recency search (headlines + snippets, last week, no extraction) used by the lead researcher to discover timely subtopics before dispatching researchers
- `reflection.py`: Reflection tool for agent self-evaluation during ReAct loops
- `notes.py`: `note_taker` (records notes as SystemMessage with slug ID) and `delete_note` (removes via RemoveMessage)
- `handoff.py`: Researcher's exit tool — writes summary + sources to state and terminates the graph via `goto=END`
- `researcher_agent_tool.py`: Agent-as-tool wrapper that invokes the researcher subagent in an isolated context window
- `middleware.py`: `ReflectionMiddleware` for injecting reflection history before each LLM call
- `_helpers.py`: `ok()`/`err()` Command builders shared by all tools
- `services/tavily.py`, `services/extract.py`: Direct SDK wrappers for Tavily Search and Extract

**Configuration** (`config/`):
- `system_prompts/`: Prompt templates for agents and nodes
- `constants.py`: Pipeline-wide tuneable constants: `WEB_SEARCH_PER_URL_CHAR_CAP`, `COMPRESSION_RATE`, `MIN_CHARS_TO_COMPRESS`, `MAX_REFLECTION_ENTRIES`, `AGENT_RECURSION_LIMIT`, `MAX_RESEARCHER_INVOCATIONS`

### Data Flow Example

1. **Trigger**: User picks a region in the portal (or `POST /api/runs`); the run is queued and picked up by the background worker thread.
2. **Agent Team**: Lead researcher dispatches researcher subagents per issue. Each researcher uses `web_search` which searches via Tavily, fetches full page content via Tavily Extract, and compresses it via static self-information scoring. The researcher reads compressed content in-context, evaluates quality, and hands off an informed summary with curated URL strings. The `web_search` tool separately pushes `{"url", "content"}` dicts to state via `operator.add`. `invoke_researcher` reconciles the curated URLs with their content dicts. `run_agent_team` collects sources, filters by reliability, and populates `legislation_content` from the content dicts.
3. **Note Taker**: LLM summarizes all compressed content blocks into dense notes
4. **Summary Writer**: LLM extracts structured data (header + bullets per item) → `WriterOutput`
5. **Report Storage**: Upserts parent `reports` row (region+date), then `report_headers` rows (one per legislation item with topic, header, bullets). Returns `report_id`.
6. **Display**: The portal polls `GET /api/reports` — the new report appears in the list when saved, and clicking it renders `GET /api/reports/{id}` (headers grouped by topic, straight from Supabase). Failures surface via the `GET /api/runs` status strip.

### Key Design Decisions

**Fixed pipeline over dynamic routing**
- Nodes execute in fixed order, making behavior predictable and debuggable
- Changes to pipeline structure happen at `pipelines/nv_local.py:chain`

**ReAct agents only for tool-use**
- Legislation discovery uses ReAct (multi-turn reasoning with tools)
- Note-taking and summary-writing are single-shot LLM transforms (simpler, cheaper)

**Source filtering in agent prompt**
- Source filtering is handled by the legislation finder agent's system prompt, which includes a classification table for accepting/rejecting sources based on type (government sites, legislative databases, factual news vs. opinion, blogs, aggregators)

**Content extraction inline in web_search (not a separate pipeline node)**
- The `web_search` tool fetches full page content via Tavily Extract and compresses it via static self-information scoring, returning compressed content directly to the researcher agent
- This gives the researcher actual content to evaluate source quality and relevance, producing content-informed summaries instead of guessing from search snippets
- Compressed content flows through state as `{"url", "content"}` dicts, populating `legislation_content` in `run_agent_team.py` without a separate content retrieval step

**Per-source context compression (static self-information pruning)**
- Each fetched page is independently compressed by `utils/content/compressor.py` inside the `web_search` tool, before entering the researcher agent's context window
- Raw content is capped at `WEB_SEARCH_PER_URL_CHAR_CAP=30_000` chars per URL before compression
- At `COMPRESSION_RATE=0.4`, each URL yields ~12K chars of compressed content; with `WEB_SEARCH_MAX_RESULTS=3` and up to 4 searches per researcher, the context budget stays manageable
- Compression is applied per-source to keep the logic local to where data enters the pipeline
- Short content (<`MIN_CHARS_TO_COMPRESS=1_000` chars) bypasses compression entirely

**Direct SDK calls for external services**
- Tavily search functions live in `tools/services/tavily.py` as direct SDK calls; tool adapters in `tools/` wrap them for LangGraph
- Tool adapters live in `tools/` with re-exports via `__init__.py`; agents import them rather than defining tools inline

**Rate limiting: bounded agent iterations**
- Pipeline nodes pass `AGENT_RECURSION_LIMIT=40` (from `config/constants.py`) at `ainvoke()` time via the `config` dict, preventing unbounded tool call loops that caused 429 Too Many Requests errors
- System prompts include explicit "Exit Criteria" sections with measurable stopping conditions
- Together these reduce LLM request volume ~40% while maintaining research quality
- Additionally, the web server serializes pipeline runs (one at a time via a single-worker executor)

**Serialized background runs, sync routes**
- One pipeline run at a time; additional runs queue FIFO in the single-worker executor
- Duplicate requests for an already-active region return 409
- Routes stay sync `def` so the pipeline's internal `asyncio.run()` never collides with a running event loop

## LLM Configuration

Default config in `utils/llm/config.py`:
- **Model**: `gpt-5`
- **Temperature**: 0.0 (deterministic)
- **Max tokens**: 16384
- **Timeout**: 120s

Use `get_llm()`, `get_mini_llm()` (same config as default), `get_structured_llm(schema)`, or `get_structured_mini_llm(schema)` to instantiate. All pull from env var `OPENAI_API_KEY`.

## External Dependencies & Environment Variables

**Core** (required):
- `OPENAI_API_KEY`: OpenAI API access
- `TAVILY_API_KEY`: Tavily Search + Extract (web search and content retrieval)
- `SUPABASE_URL`, `SUPABASE_KEY`: Region/topic config + report storage

**Server** (optional):
- `HOST`: bind address (default `0.0.0.0`)
- `PORT`: listen port (default `8000`)

All come from `.env` (loaded automatically) or the process environment.

## Common Patterns

**State Passing**
- Pipeline state is a `ChainData` TypedDict. Each node receives it as input, modifies relevant fields, and returns it.
- Example: `legislation_finder_node` receives `{"region": str, "topic": str}`, returns `{"region": str, "topic": str, "legislation_sources": list[str], ...}`

**LLM Calls**
- Structured output: use `get_structured_llm(OutputSchema)` → returns a Runnable that enforces schema
- Unstructured: use `get_llm()` → invoke with list of messages

**Agents**
- Built with `create_agent` from `langchain.agents` (see `agents/researcher_agent.py` for pattern)
- Tools live in `tools/` and are imported directly; agents compose their tool list at build time (e.g., `from tools import web_search, reflection_tool`)
- Each tool adapter calls service functions from `tools/services/tavily.py` and returns a LangGraph `Command` for state updates
- `ReflectionMiddleware` in `tools/middleware.py` injects reflection history before each LLM call; add it to the `middleware` list when building agents that use `reflection_tool`
- The agent-as-tool pattern (`tools/researcher_agent_tool.py`) wraps a subagent invocation as a tool, giving it an isolated context window
- `response_format` on `create_agent` enforces structured output schemas (e.g., `LeadResearcherOutput`); the researcher uses a `handoff` tool instead of `response_format` for its exit
- `recursion_limit` is applied at invoke-time via the config dict; `MAX_RESEARCHER_INVOCATIONS` limits subagent dispatch at the tool level via `InjectedState`

**Error Handling**
- Classifier output parse failures → reject all sources (safe fallback)
- Pipeline exceptions mark the run `failed` with the error string on the run record
- Per-topic save failures are recorded in the run's `failures` list; any failure marks the run `failed`
- `save_report()` returning `None` is treated as a per-topic failure
- Failure detail is surfaced via `GET /api/runs/{id}` and the portal, plus stderr logs

## Code Conventions

- **Typed data structures**: Use `TypedDict` or Pydantic models at pipeline boundaries (between nodes, agents, external APIs)
- **No dedicated config file**: Configuration is inlined (e.g., `DEFAULT_LLM_CONFIG` in `utils/llm/config.py`)
- **Minimal dependencies**: Only essential packages in `requirements.txt`
- **Docstrings**: Required for all functions, classes, and methods
- **Linting**: Ruff linter + formatter, configured in `pyproject.toml`. Run `ruff check --fix . && ruff format .` before committing, or rely on the pre-commit hook

## Deployment

**Local**: `python main.py` → portal at `http://localhost:8000`

**Docker**:
```bash
docker build -f docker/Dockerfile -t nv-local .
docker run -p 8000:8000 --env-file .env nv-local
```

**Logs**: Emitted to stdout/stderr.

## Important Known Issues / WIP

- Tavily Extract can fail on some domains (access restrictions, JS-heavy SPAs); when extraction fails for a URL, `web_search` returns an empty content string and the researcher works from search snippets only
- Run status is ephemeral and in-memory — a server restart clears in-flight/failed statuses (reports remain in Supabase and re-appear in the portal), and a run in flight during shutdown is lost

## Common Development Tasks

**Adding a new pipeline node**:
1. Create file in `pipelines/node/<node_name>.py`
2. Define node as a `RunnableSequence` or callable
3. Insert into `pipelines/nv_local.py:chain` in correct position
4. Update `utils/schemas/state.py:ChainData` if new state fields are needed
5. Document in `docs/ARCHITECTURE.md`

**Adding an agent tool**:
1. Create the tool function in `tools/` with the LangChain `@tool` decorator; return a `Command` using `ok()`/`err()` from `tools/_helpers.py`
2. If the tool needs an external service, add the business logic in `tools/services/` (e.g., `tools/services/tavily.py`)
3. Import the tool in the agent file (e.g., `from tools import web_search`) and include it in the `tools` list when calling `create_agent`

**Adding an API endpoint**:
1. Add the route to `api/app.py` as a plain `def` (never `async def` — see the asyncio constraint above)
2. Keep run-registry logic in `api/runs.py`; `app.py` handles HTTP concerns only
3. Add endpoint tests to `tests/integration/test_api.py` using `TestClient`

**Changing LLM model or config**:
1. Update `utils/llm/config.py:DEFAULT_LLM_CONFIG`
2. Note: All LLM factory functions reference this dict, so one change affects all calls

**Debugging a region pipeline failure**:
1. Trigger the region from the portal, then check `GET /api/runs/{id}` for `error`/`failures`
2. Check error detail in server stdout/stderr
3. Likely causes: missing env vars (`OPENAI_API_KEY`, `TAVILY_API_KEY`), Tavily Extract failure on a domain, agent hitting `recursion_limit=40` before completing, or the region missing from the Supabase `supported_regions` table

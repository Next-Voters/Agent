# Operations

This document describes how NV Local is run in development and in a container.

## Environments

- Local dev: `python main.py` from a virtualenv (or `uvicorn api.app:app --reload` for auto-reload)
- Container: build and run `docker/Dockerfile`, publishing port 8000

## Configuration And Secrets

Core runtime secrets:

- `OPENAI_API_KEY`: OpenAI API access
- `TAVILY_API_KEY`: Tavily Search + Extract (web search and content retrieval)
- `SUPABASE_URL`, `SUPABASE_KEY`: City/topic config + report storage

Server config (optional):

- `HOST`: bind address (default `0.0.0.0`)
- `PORT`: listen port (default `8000`)

Operational guidance:

- Prefer injecting secrets via your environment (shell export or container env vars).
- `main.py` calls `dotenv.load_dotenv()`, so a `.env` file is loaded automatically.

## Running

### Local

```bash
python main.py
```

Then open `http://localhost:8000` for the portal, or use the API directly:

| Method/Path | Behavior |
|---|---|
| `GET /` | Portal page |
| `GET /api/regions` | List supported regions (from Supabase) |
| `POST /api/runs` `{"region": ...}` | Start a run — `202` accepted, `400` unknown region, `409` region already queued/running, `502` Supabase unreachable |
| `GET /api/runs` | Ephemeral per-region run statuses (queued/running/failed) |
| `GET /api/reports` | Saved reports from Supabase, newest first |
| `GET /api/reports/{id}` | One report with headers inner-joined, grouped by topic |

### Container

```bash
docker build -f docker/Dockerfile -t nv-local .
docker run -p 8000:8000 --env-file .env nv-local
```

### Run Lifecycle

- **Runs are not stored locally.** Reports are read back from Supabase (`reports` inner-joined with `report_headers`); the server keeps only ephemeral per-region status while a run is queued/running, plus the last failure per region until it is re-run.
- Runs execute **one at a time** on a background worker thread; additional runs queue FIFO. A second request for a region that is already queued/running is rejected with `409`.
- A run in flight when the server shuts down is lost; re-trigger it after restart.
- On success the status entry disappears and the report appears in `GET /api/reports`. On failure the status carries an `error` (pipeline exception) and/or `failures` (per-topic save failures).

## Logging And Monitoring

- Primary logs: stdout/stderr from the server process.
- Per-topic pipeline failures are logged to stderr and recorded on the run object, visible via `GET /api/runs/{id}` and in the portal.

## Data Storage And Backups

- Reports are stored in the Supabase `reports` table (upserted per region/topic).
- Supported regions and topics are read from Supabase (`supported_regions` and related tables).
- Backups, retention, and schema migrations are owned by the Supabase project.

## Runbooks

### Run Fails Immediately

1) Check server logs for missing env vars (common: `OPENAI_API_KEY` or `TAVILY_API_KEY`).
2) A `502` from `/api/regions` or `POST /api/runs` means Supabase is unreachable or `SUPABASE_URL`/`SUPABASE_KEY` are unset.

### Tavily Search / Extract Errors

Symptoms: empty legislation sources or empty content blocks.

1) Verify `TAVILY_API_KEY` is present in the runtime environment.
2) Tavily Extract can fail on JS-heavy SPAs or access-restricted domains; when extraction fails for a URL the researcher works from search snippets only.
3) If failures are widespread, check Tavily service status.

### OpenAI Errors / Rate Limits

1) Verify `OPENAI_API_KEY` and account quota.
2) The agent `recursion_limit` (configured in `config/constants.py`) bounds tool-call loops to prevent runaway API usage.
3) Runs are already serialized (one pipeline at a time), which keeps request volume bounded.

### Investigating A Failed Run

`GET /api/runs` returns the failure detail for the region (kept until the region is re-run):

- `error`: the pipeline exception, if the chain itself failed
- `failures`: labels of topics whose reports failed to save (e.g., `"toronto (housing)"`)

Cross-reference with server logs, then check `reports`/`report_headers` in Supabase for partial data (a report may exist with only some topics saved).

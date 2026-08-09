<div align="center">

  <h1>Next Voters Local</h1>
  <p><strong>Hold your city accountable to their actions.</strong></p>
  <p>AI agents that research municipal legislation so you don't have to.</p>
  <p>
    <a href="https://github.com/Next-Voters/Agent/stargazers"><img src="https://img.shields.io/github/stars/Next-Voters/Agent" alt="Stars" /></a>
    <a href="https://github.com/Next-Voters/Agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License" /></a>
    <a href="https://github.com/Next-Voters/Agent/issues"><img src="https://img.shields.io/github/issues/Next-Voters/Agent" alt="Issues" /></a>
  </p>
</div>

---

Next Voters uses AI agents to find, research, and summarize municipal legislation — making government information accessible to communities that cannot afford the time or resources to track what their local officials are doing.

Many people — working families, elderly residents, anyone already stretched thin — are effectively locked out of the legislative process simply because keeping up with city council agendas is a full-time job. Next Voters automates that work so you don't have to through an AI agent!

## What It Does

- **Discovers** recent legislation across multiple cities using AI-powered web search
- **Researches** each piece of legislation with specialized AI agents that classify sources, extract key details, and provide political context
- **Summarizes** everything into clear, readable reports so anyone can understand what's happening in their city

## Architecture At A Glance

Next Voters is a multi-agent research pipeline behind a small web portal. A FastAPI server serves the portal and a JSON API; each run discovers legislation sources, fetches and extracts content, and produces a structured summary — all orchestrated by LangGraph-based agents on a background worker thread, with reports saved to and served from Supabase. The portal itself is a Svelte app (built into `api/static/dist/`) that lists reports per city and lets you drill into or delete any of them.

For the full picture — agent design, database schema, and operations — see the [architecture documentation](docs/ARCHITECTURE.md).

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py         # serves http://localhost:8000
```

Open `http://localhost:8000` to pick a region, start a run, and browse saved reports grouped by city — delete any report you no longer need. The same functionality is available over the API:

```bash
curl http://localhost:8000/api/regions                # list supported regions
curl -X POST http://localhost:8000/api/runs \
     -H 'Content-Type: application/json' \
     -d '{"region": "toronto"}'                       # start a run
curl http://localhost:8000/api/runs                   # poll ephemeral run status
curl http://localhost:8000/api/reports                # list saved reports
curl http://localhost:8000/api/reports/<report_id>    # one report, headers by topic
curl -X DELETE http://localhost:8000/api/reports/<report_id>  # delete a report
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — index of all design, infrastructure, and operations docs
- [Operations](docs/OPERATIONS.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT: see `LICENSE`.

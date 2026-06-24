<div align="center">

  <h1>Next Voters Local</h1>
  <p><strong>Hold your city accountable to their actions.</strong></p>
  <p>AI agents that research municipal legislation so you don't have to.</p>
  <p>
    <a href="https://github.com/Next-Voters/Local/stargazers"><img src="https://img.shields.io/github/stars/Next-Voters/Local" alt="Stars" /></a>
    <a href="https://github.com/Next-Voters/Local/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License" /></a>
    <a href="https://github.com/Next-Voters/Local/issues"><img src="https://img.shields.io/github/issues/Next-Voters/Local" alt="Issues" /></a>
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

Next Voters is a multi-agent research pipeline. Each run discovers legislation sources, fetches and extracts content, and produces a structured summary — all orchestrated by LangGraph-based agents. It runs as standalone software via CLI or Docker container.

For the full picture — agent design, AWS deployment, database schema, and operations — see the [architecture documentation](docs/ARCHITECTURE.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — index of all design, infrastructure, and operations docs
- [Operations](docs/OPERATIONS.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT: see `LICENSE`.

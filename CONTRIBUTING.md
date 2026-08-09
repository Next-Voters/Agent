# Contributing

This project is a small Python codebase: a FastAPI web portal that triggers a multi-agent research pipeline.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment variables:

- Copy `.env.example` to `.env` and set required keys.
- `main.py` calls `dotenv.load_dotenv()`, so a `.env` file is loaded automatically.

## Running Locally

Start the web server and open the portal at `http://localhost:8000`:

```bash
python main.py
```

For development with auto-reload:

```bash
uvicorn api.app:app --reload
```

Or build and run the container image:

```bash
docker build -f docker/Dockerfile -t nv-local .
docker run -p 8000:8000 --env-file .env nv-local
```

## Testing

```bash
pytest tests
```

Quick non-destructive checks you can run:

```bash
python -m compileall -q .
```

## Linting / Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting,
enforced at two levels:

- **Pre-commit hook** — lightweight slop-catcher that blocks glaring issues
  (dead code, unused imports, commented-out code, whitespace junk, syntax errors)
- **CI** — comprehensive lint + format check on every push and PR to `main`

### One-time setup

```bash
pip install -r requirements-dev.txt
pre-commit install
```

After this, every `git commit` will automatically catch:
- Unused imports and variables (dead code)
- Undefined names
- Commented-out code left behind
- Trailing whitespace and missing newlines
- Syntax errors (`compileall`)

The full rule set (import ordering, code style, format) is enforced by CI.

### Manual checks

```bash
# Quick lint (same rules as pre-commit)
ruff check --select "F,W,ERA,PIE790" .

# Full lint (same rules as CI)
ruff check .

# Format
ruff format .
```

Configuration lives in `pyproject.toml` under `[tool.ruff]`.

### Guidelines

- Keep changes focused and consistent with nearby code.
- Prefer explicit, typed data structures (`TypedDict` / Pydantic models) where the pipeline crosses boundaries.
- Avoid introducing new runtime dependencies unless necessary.

## Branching

- Create feature branches off `main`: `feature/<short-description>` or `fix/<short-description>`
- Keep PRs small and focused.

## Pull Request Checklist

- [ ] The change is scoped and explained (what + why)
- [ ] `pre-commit run --all-files` passes (or `ruff check . && ruff format --check .`)
- [ ] Any new env vars are documented in `README.md` and/or `docs/OPERATIONS.md`
- [ ] Any behavior changes to the pipeline are reflected in `docs/ARCHITECTURE.md`

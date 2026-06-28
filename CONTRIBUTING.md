# Contributing

This project is a small Python codebase that runs as a container, driven by the `REGION` environment variable.

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

The pipeline runs in container mode, selecting its region from the `REGION` env var:

```bash
REGION=<region> python main.py
```

Or build and run the container image:

```bash
docker build -f docker/Dockerfile -t nv-local .
docker run -e REGION=<region> --env-file .env nv-local
```

## Testing

There is no dedicated test suite in this repository at the moment.

Quick non-destructive checks you can run:

```bash
python -m compileall -q .
```

If you add tests, include how to run them in your PR description and consider updating this file.

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

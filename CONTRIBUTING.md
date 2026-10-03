# Contributing

Thanks for your interest in contributing! Here's how to get started.

## Bug Reports & Feature Requests

Open a [GitHub Issue](../../issues/new) with:
- Clear description of the problem or idea
- Steps to reproduce (for bugs)
- Expected vs actual behavior

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Make your changes with clear commit messages
4. Run existing tests to ensure nothing breaks
5. Open a PR with a description of what changed and why

## Development Setup

See the README for installation and setup instructions.

## Code Style

- Follow the existing patterns in the codebase
- Use meaningful variable and function names
- Add comments only where the logic isn't self-evident

## Verification

Run backend commands from the repository root with Python 3.11+ (CI uses 3.11).
Use an isolated virtual environment; the development extra supplies pytest, and
FastAPI's TestClient also needs `httpx`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' httpx
# Focused configuration and in-memory SQLite fixtures
.venv/bin/python -m pytest tests/test_config.py tests/test_connection.py -q
# Broader backend suite, matching the pytest lane in CI
.venv/bin/python -m pytest tests/ -v
```

The suite uses explicit in-memory/temporary SQLite databases, synthetic posts,
and mocked provider clients; Reddit/Anthropic credentials and Keychain setup are
not test prerequisites. Do not start ingestion or seed subreddits for these tests.
On Windows use the virtual environment's `Scripts/python.exe` path.

For the dashboard, use a Node version supported by the committed frontend lock
(Node 22.13+ on 22.x or Node 24 is suitable for its Vite/ESLint tooling):

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Installation needs package access. There is no frontend test script, standalone
typecheck, formatter check, or configured Python lint command. `make install`,
`make test`, and `make lint` are shortcuts using the active Python environment
and the installed frontend dependencies; they do not add missing tooling.

For changed dashboard behavior, run `npm run dev` and verify empty/error/loading
states, filters, chart/tooltips, and keyboard navigation against mocked `/api`
responses in the browser. No browser automation harness is configured. Real
`make run`/Uvicorn startup creates the configured application database under
`~/Library/Application Support`; live ingestion and credential setup are separate
operations. Pure documentation changes need no browser walkthrough.

## Questions?

Open an issue or start a discussion. Response time is typically within a few days.

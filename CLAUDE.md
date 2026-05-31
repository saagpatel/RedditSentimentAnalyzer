# Reddit Sentiment Analyzer

Local-first tool to monitor sentiment trends across subreddits over time. Ingests posts and comments via PRAW, scores them with VADER, stores in SQLite, and serves a React dashboard showing time-series sentiment trends with spike detection and drill-down.

## Stack

| Layer | Tech | Version |
|-------|------|---------|
| Reddit ingestion | PRAW | 7.7.1 |
| Sentiment scoring | vaderSentiment | 3.3.2 |
| Database | SQLite | bundled |
| API server | FastAPI + Uvicorn | 0.111.0 / 0.29.0 |
| Task scheduler | APScheduler | 3.10.4 |
| LLM escalation (optional) | Anthropic SDK | 0.25.0 |
| Frontend | React 19 + Vite 8 | — |
| Charts | Recharts | 3.x |
| Word cloud | D3 | 7.x |

## Build / Run

```bash
# Start the FastAPI backend
uv run uvicorn backend.main:app --reload

# Start the React dashboard (separate terminal)
cd frontend && npm install && npm run dev

# Start the ingestion daemon standalone
uv run python -m backend.ingestion.ingest_daemon
```

## Conventions

- All SQL lives in `backend/db/queries.py` — no inline SQL in routes or processors.
- Rate limiter caps PRAW at 80 req/min (API ceiling: 100 — stay under).
- Store secrets (Reddit + Anthropic credentials) in macOS Keychain via `keyring`; never in `.env` or plaintext files.
- VADER scores all posts. LLM escalation fires only when `|compound| < 0.05` AND `LLM_ESCALATION_ENABLED=True` in config.
- Comment depth: Phase 0–1 ingest top-level only (`depth == 0`); `depth <= 2` added in Phase 2.
- Sentiment buckets aggregate to 6-hour windows — changing this requires matching updates to frontend chart logic.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Auth | PRAW read-only script OAuth2 — no user context, no posting |
| Data storage | SQLite in `~/Library/Application Support/reddit-sentiment/` |
| Spike threshold | `delta_compound >= 0.3` over prior 6h bucket |
| LLM escalation threshold | `|vader_compound| < 0.05` |
| Escalation cap | 50 LLM calls/ingest cycle max |
| Historical pull | First run: `.hot()` + `.top(time_filter='week')` — subsequent: `.new()` incremental |

## Constraints

- Credentials: Keychain via `keyring` only — no `.env`, no plaintext, no committed secrets.
- Persistence: all data stays local; no cloud sync or external data persistence.
- Schema changes: run a migration script before altering the SQLite schema.
- Database: SQLite only until 10M+ row threshold; no Postgres.
- LLM escalation: guarded by `LLM_ESCALATION_ENABLED=True` — never fire on render or in scheduled loops without the config flag.
- Scope: implement only features in the current phase; no speculative additions.

<!-- portfolio-context:start -->
# Portfolio Context

## What This Project Is

RedditSentimentAnalyzer is a local-first dashboard for tracking sentiment trends across selected subreddits over time. It ingests Reddit posts/comments, stores historical samples in SQLite, scores sentiment with VADER by default, optionally escalates ambiguous cases to an LLM, and exposes trends, word clouds, and alerts through a FastAPI + React interface.

## Current State

**Phases 0–3 complete** — all pipeline stages implemented (ingestion, VADER scoring, API, React dashboard, LLM escalation). Spike detection operational. See IMPLEMENTATION-ROADMAP.md for full acceptance criteria.

## Stack

| Layer | Tech | Version |
|-------|------|---------|
| Reddit ingestion | PRAW | 7.7.1 |
| Sentiment scoring | vaderSentiment | 3.3.2 |
| Database | SQLite | bundled |
| API server | FastAPI + Uvicorn | 0.111.0 / 0.29.0 |
| Task scheduler | APScheduler | 3.10.4 |
| LLM escalation (optional) | Anthropic SDK | 0.25.0 |
| Frontend | React 19 + Vite 8 | — |
| Charts | Recharts | 3.x |
| Word cloud | D3 | 7.x |

## How To Run

```bash
# Start the FastAPI backend
uv run uvicorn backend.main:app --reload

# Start the React dashboard (separate terminal)
cd frontend && npm install && npm run dev

# Or start the ingestion daemon standalone
uv run python -m backend.ingestion.ingest_daemon
```

## Known Risks

- Do not write credentials to `.env`, config files, or any file that could be committed
- Do not add cloud sync or any external data persistence — all data stays local
- Do not change the SQLite schema without running a migration script
- Do not add Postgres or any other database — SQLite until 10M+ row threshold
- Do not add features not in the current phase
- Do not fire LLM escalation on render or in scheduled loops without the config flag explicitly enabled

## Next Recommended Move

Use this context plus the README and supporting docs to resume the next active task, then promote the repo beyond minimum-viable by capturing a dedicated handoff, roadmap, or discovery artifact.

<!-- portfolio-context:end -->

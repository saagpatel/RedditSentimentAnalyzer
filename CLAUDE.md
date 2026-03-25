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
| Frontend | React 18 + Vite 5 | — |
| Charts | Recharts | 2.x |
| Word cloud | D3 | 7.x |

## Current Phase

**Phase 0: Foundation** — See IMPLEMENTATION-ROADMAP.md for tasks, acceptance criteria, and verification checklists.

## Development Conventions

- All SQL lives in `backend/db/queries.py` — no inline SQL in routes or processors
- Rate limiter must cap PRAW at 80 req/min (ceiling 100 — stay under)
- Secrets (Reddit + Anthropic credentials) stored in macOS Keychain via `keyring` — never in `.env` or plaintext
- VADER scores all posts. LLM escalation only fires when `|compound| < 0.05` AND `LLM_ESCALATION_ENABLED=True` in config
- Comment depth: Phase 0-1 ingest top-level only (`depth == 0`). `depth <= 2` added in Phase 2
- Sentiment buckets aggregate to 6-hour windows — do not change this without updating frontend chart logic

## Key Decisions

| Decision | Choice |
|----------|--------|
| Auth | PRAW read-only script OAuth2 — no user context, no posting |
| Data storage | SQLite in `~/Library/Application Support/reddit-sentiment/` |
| Spike threshold | `delta_compound >= 0.3` over prior 6h bucket |
| LLM escalation threshold | `|vader_compound| < 0.05` |
| Escalation cap | 50 LLM calls/ingest cycle max |
| Historical pull | First run: `.hot()` + `.top(time_filter='week')` — subsequent: `.new()` incremental |

## Do NOT

- Do not write credentials to `.env`, config files, or any file that could be committed
- Do not add cloud sync or any external data persistence — all data stays local
- Do not change the SQLite schema without running a migration script
- Do not add Postgres or any other database — SQLite until 10M+ row threshold
- Do not add features not in the current phase
- Do not fire LLM escalation on render or in scheduled loops without the config flag explicitly enabled

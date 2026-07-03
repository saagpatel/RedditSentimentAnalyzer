<!-- portfolio-context:start -->
# Portfolio Context

## What This Project Is

RedditSentimentAnalyzer: Reddit Sentiment Analyzer is a local-first tool that monitors sentiment trends across subreddits over time. Posts and comments are fetched via PRAW, scored with VADER, and served through a FastAPI backend to a React dashboard with spike detection and optional Claude escalation for ambiguous signals.

## Current State

Portfolio truth currently marks this project as `active` with `boilerplate` context. Phase 104 recovered minimum-viable context so future sessions can resume without rediscovery.

## Stack

| Layer | Technology |
|-------|------------|
| Ingestion | PRAW 7.7+, APScheduler 3.10 |
| Sentiment | vaderSentiment 3.3+ |
| Backend | FastAPI 0.111+, Uvicorn, Pydantic v2 |
| Database | SQLite (local, no server) |
| Frontend | React 19, Recharts |
| LLM (optional) | Anthropic Claude via `anthropic` SDK |

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

- This repo only has minimum-viable recovery context today; deeper handoff details may still live in the README and supporting docs.

## Next Recommended Move

Use this context plus the README and supporting docs to resume the next active task, then promote the repo beyond minimum-viable by capturing a dedicated handoff, roadmap, or discovery artifact.

<!-- portfolio-context:end -->

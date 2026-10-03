# Reddit Sentiment Analyzer

[![CI](https://github.com/saagpatel/RedditSentimentAnalyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/saagpatel/RedditSentimentAnalyzer/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python)](https://www.python.org/) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](./LICENSE)

> Track how the internet feels about anything — without the cloud

Reddit Sentiment Analyzer is a local-first tool that monitors sentiment trends across subreddits over time. Posts and comments are fetched via PRAW, scored with VADER, and served through a FastAPI backend to a React dashboard with spike detection and optional Claude escalation for ambiguous signals.

## Features

- **Background ingestion daemon** — polls tracked subreddits every 15 minutes via APScheduler; seeds with `.hot()` + `.top(week)` on first run, then pulls `.new()` incrementally
- **VADER scoring** — compound, positive, negative, and neutral scores stored per post and comment
- **6-hour sentiment buckets** — pre-aggregated time-windowed averages; the API combines them into 12h and 1d windows, carrying forward existing spike flags
- **Spike detection** — flags 6h buckets where the absolute compound-score change from the immediately preceding bucket meets or exceeds a configurable threshold
- **React dashboard** — time series chart, multi-subreddit comparison, word cloud, and spike detail panel
- **Optional Claude escalation** — ambiguous posts routed to Claude for deeper classification with reasoning (disabled by default)
- **macOS Keychain secrets** — credentials stored with `keyring`; no `.env` files with tokens on disk

## Quick Start

### Prerequisites
- **macOS-oriented setup** — credentials are accessed through `keyring`, and the default database path uses `~/Library/Application Support`; the application has no explicit macOS-only platform check
- Python 3.11+
- Reddit API credentials (client ID + secret from https://www.reddit.com/prefs/apps)
- `uv` (recommended) or `pip`

### Installation
```bash
git clone https://github.com/saagpatel/RedditSentimentAnalyzer
cd RedditSentimentAnalyzer
uv sync
```

### Credentials setup
Store Reddit API credentials in macOS Keychain before starting the server (one-time step):
```bash
uv run python scripts/setup_keyring.py
```

### Usage
```bash
# Start the FastAPI backend
uv run uvicorn backend.main:app --reload

# Start the React dashboard (separate terminal)
cd frontend && npm install && npm run dev

# Or start the ingestion daemon standalone
uv run python -m backend.ingestion.ingest_daemon
```

## Tech Stack

For credential-free fixture tests and frontend lint/build checks, see
[Contributing: verification](CONTRIBUTING.md#verification). Starting the backend,
seeding subreddits, and running ingestion use application data or providers and
are separate from that verification lane.

| Layer | Technology |
|-------|------------|
| Ingestion | PRAW 7.7+, APScheduler 3.10+ |
| Sentiment | vaderSentiment 3.3+ |
| Backend | FastAPI 0.111+, Uvicorn, Pydantic v2 |
| Database | SQLite (local, no server) |
| Frontend | React 19, Recharts |
| LLM (optional) | Anthropic Claude via `anthropic` SDK |

## Architecture

The ingestion daemon and the FastAPI server share a single SQLite database. The daemon writes to `posts`, `comments`, and `sentiment_buckets` tables; the API reads from them with no coupling beyond the schema. Bucket aggregation runs after each ingest cycle that fetches posts, using SQL `GROUP BY` over the raw post scores; the API combines 6h buckets into 12h and 1d windows in memory. The React dashboard re-fetches trend and word-cloud data from the REST API when the subreddit or time range changes; comparison data is fetched when Compare is submitted, rendering multi-series Recharts line charts with React state for filter/comparison controls.

## Configuration

Subreddits to ingest, polling interval, spike detection threshold, and other settings are configured directly in `backend/config.py`. `uv run python scripts/seed_subreddits.py` adds the fixed list in `SEED_SUBREDDITS` to the database; it does not update the daemon's configured subreddit list.

## License

MIT

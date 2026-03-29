# Reddit Sentiment Analyzer

[![Python](https://img.shields.io/badge/Python-3776ab?style=flat-square&logo=python)](#) [![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](#)

> Track how the internet feels about anything — without the cloud

Reddit Sentiment Analyzer is a local-first tool that monitors sentiment trends across subreddits over time. Posts and comments are fetched via PRAW, scored with VADER, and served through a FastAPI backend to a React dashboard with spike detection and optional Claude escalation for ambiguous signals.

## Features

- **Background ingestion daemon** — polls tracked subreddits every 15 minutes via APScheduler; seeds with `.hot()` + `.top(week)` on first run, then pulls `.new()` incrementally
- **VADER scoring** — compound, positive, negative, and neutral scores stored per post and comment
- **6-hour sentiment buckets** — pre-aggregated time-windowed averages with spike detection at 6h, 12h, and 1d resolution
- **Spike detection** — flags buckets where compound score deviates beyond a configurable threshold
- **React dashboard** — time series chart, multi-subreddit comparison, word cloud, and spike detail panel
- **Optional Claude escalation** — ambiguous posts routed to Claude for deeper classification with reasoning (disabled by default)
- **macOS Keychain secrets** — credentials stored with `keyring`; no `.env` files with tokens on disk

## Quick Start

### Prerequisites
- Python 3.11+
- Reddit API credentials (client ID + secret from https://www.reddit.com/prefs/apps)
- `uv` (recommended) or `pip`

### Installation
```bash
git clone https://github.com/saagpatel/RedditSentimentAnalyzer
cd RedditSentimentAnalyzer
uv sync
```

### Usage
```bash
# Start the FastAPI backend
uv run uvicorn app.main:app --reload

# Start the React dashboard (separate terminal)
cd frontend && npm install && npm run dev

# Or start the ingestion daemon standalone
uv run python -m app.daemon
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Ingestion | PRAW 7.7+, APScheduler 3.10 |
| Sentiment | vaderSentiment 3.3+ |
| Backend | FastAPI 0.111+, Uvicorn, Pydantic v2 |
| Database | SQLite (local, no server) |
| Frontend | React 19, Recharts, shadcn/ui |
| LLM (optional) | Anthropic Claude via `anthropic` SDK |

## Architecture

The ingestion daemon and the FastAPI server share a single SQLite database. The daemon writes to `posts`, `comments`, and `sentiment_buckets` tables; the API reads from them with no coupling beyond the schema. Bucket aggregation is a scheduled APScheduler job that runs SQL window functions over the raw scores — no in-memory aggregation. The React dashboard polls the REST API on a 60-second interval and renders multi-series Recharts line charts with Zustand state for filter/comparison controls.

## License

MIT
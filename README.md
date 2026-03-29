# Reddit Sentiment Analyzer

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)

A local-first tool that monitors sentiment trends across subreddits over time. Posts and comments are fetched via PRAW, scored with VADER, and served through a FastAPI backend to a React dashboard.

## Features

- **Background ingestion daemon** — polls tracked subreddits every 15 minutes via APScheduler; first run seeds `.hot()` + `.top(week)`, subsequent runs pull `.new()` incrementally
- **VADER sentiment scoring** — compound, positive, negative, and neutral scores stored per post and comment
- **6-hour sentiment buckets** — pre-aggregated into time-windowed averages with spike detection; queryable at 6h, 12h, and 1d resolution
- **Spike detection** — flags buckets where compound score deviates beyond a configurable threshold
- **Optional LLM escalation** — ambiguous posts (low VADER confidence) can be rerouted to Claude for deeper classification with reasoning; disabled by default
- **React dashboard** — time series chart, multi-subreddit comparison, word cloud, and spike detail panel
- **Credentials via macOS Keychain** — no `.env` files; secrets stored with `keyring`

## Tech Stack

| Layer | Technology |
|-------|------------|
| Ingestion | PRAW 7.7+, APScheduler 3.10 |
| Sentiment | vaderSentiment 3.3+ |
| Backend | FastAPI 0.111+, Uvicorn, Pydantic v2 |
| Database | SQLite (local, no server required) |
| LLM (optional) | Anthropic Claude via `anthropic` SDK |
| Frontend | React 19, Recharts, D3, Vite |

## Prerequisites

- Python 3.11+
- Node.js 18+
- macOS (credentials use macOS Keychain via `keyring`)
- A Reddit script-type app — register at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)

## Getting Started

**1. Install Python dependencies**

```bash
pip install -e ".[dev]"
```

**2. Store Reddit credentials in Keychain**

```bash
python scripts/setup_keyring.py
```

This prompts for your Reddit `client_id` and `client_secret` and stores them securely. It also verifies the PRAW connection before exiting.

**3. Start the ingest daemon**

```bash
python -m backend.ingestion.ingest_daemon
```

To run a single cycle and exit (useful for testing):

```bash
python -m backend.ingestion.ingest_daemon --once --subreddit nba
```

**4. Start the API server**

```bash
uvicorn backend.main:app --reload
```

The API runs on `http://localhost:8000`. Health check: `GET /health`.

**5. Start the frontend**

```bash
cd frontend
npm install
npm run dev
```

The dashboard opens at `http://localhost:5173`.

## Project Structure

```
RedditSentimentAnalyzer/
├── backend/
│   ├── api/
│   │   └── routes/         # FastAPI routers: sentiment, posts, spikes
│   ├── db/
│   │   ├── schema.sql       # SQLite schema (auto-deployed on startup)
│   │   └── queries.py       # All DB queries
│   ├── ingestion/
│   │   ├── ingest_daemon.py # Scheduler + ingest orchestration
│   │   ├── praw_client.py   # Reddit API client with rate limiting
│   │   └── post_processor.py# VADER scoring per post/comment
│   ├── llm/
│   │   └── escalation.py    # Optional Claude escalation for ambiguous posts
│   ├── config.py            # Typed config (Pydantic), no .env
│   └── main.py              # FastAPI app + CORS + lifespan
├── frontend/
│   └── src/
│       ├── views/           # TimeSeriesView, ComparisonView, WordCloudView
│       └── components/      # SubredditSelector, SpikeDetailPanel, etc.
├── scripts/
│   └── setup_keyring.py     # One-time credential setup
└── tests/
```

## Screenshot

![Dashboard screenshot](docs/screenshot.png)

_Screenshot placeholder — run the app and capture your own._

## License

MIT — see [LICENSE](LICENSE).

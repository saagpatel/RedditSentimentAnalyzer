# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2024-01-01

### Added
- PRAW-based Reddit ingestion daemon with APScheduler (15-minute polling, first-run deep pull via `.hot()` + `.top(week)`)
- VADER sentiment scoring for posts and top-level comments (compound, positive, negative, neutral scores)
- 6-hour bucket aggregation with spike detection (configurable threshold)
- FastAPI backend with `/api/sentiment/timeseries`, `/api/sentiment/compare`, `/api/posts/top`, `/api/posts/:id`, and `/api/spikes` endpoints
- React + Vite dashboard with time-series chart, multi-subreddit comparison view, spike drill-down panel, and word cloud
- macOS Keychain credential storage via `keyring` — no secrets on disk
- SQLite persistence in `~/Library/Application Support/reddit-sentiment/`
- Optional Claude LLM escalation for ambiguous posts (disabled by default, controlled via `config.py`)
- One-time setup scripts: `scripts/setup_keyring.py` and `scripts/seed_subreddits.py`

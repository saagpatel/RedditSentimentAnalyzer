# Reddit Sentiment Analyzer — Frontend

React + Vite dashboard for the Reddit Sentiment Analyzer backend.

## What it is

A local React dashboard that visualizes subreddit sentiment over time. Features include a time-series chart with spike flags, multi-subreddit comparison, spike drill-down panel, and a word cloud. Data is served from the FastAPI backend running on `localhost:8000`.

## Development

```bash
npm install
npm run dev
```

The dev server runs on `http://localhost:5173`. API calls are proxied to the FastAPI backend — see `vite.config.js` for the proxy configuration. The backend must be running before the dashboard will show data.

## Environment

No `.env` file is needed. The Vite proxy in `vite.config.js` handles routing `/api` requests to the backend. Reddit credentials are stored in macOS Keychain via the backend — the frontend has no direct access to secrets.

## More

See the [root README](../README.md) for full setup instructions, architecture overview, and credential setup steps.

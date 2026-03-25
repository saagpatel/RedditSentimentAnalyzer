# Reddit Sentiment Analyzer — Implementation Roadmap

## System Architecture

```
[PRAW Ingest Daemon]
    ↓ (script OAuth2, token-bucket rate limiter at 80 req/min)
[Raw Post + Comment Buffer]
    ↓
[VADER Scorer]
    → compound, pos, neg, neu scores per post + top-level comment
    ↓ (if |compound| < 0.05 AND LLM_ESCALATION_ENABLED=True)
[LLM Escalation] → Anthropic API → structured (label, confidence, reasoning)
    ↓
[SQLite — reddit_sentiment.db]
    ↓
[FastAPI + APScheduler]
    ↓ REST endpoints
[React Frontend (Vite)]
    ├── TimeSeriesView — Recharts LineChart, 6h buckets, spike flags
    ├── ComparisonView — multi-subreddit overlay
    ├── SpikeDetailView — drill-down panel, top posts by sentiment
    └── WordCloudView — D3 term frequency, updates with time range
```

## File Structure

```
reddit-sentiment/
├── CLAUDE.md
├── IMPLEMENTATION-ROADMAP.md
├── pyproject.toml
├── .env.example                      # Template only — no real secrets
├── backend/
│   ├── main.py                       # FastAPI app, mounts routers
│   ├── config.py                     # Settings: subreddits, keywords, thresholds, flags
│   ├── ingestion/
│   │   ├── praw_client.py            # PRAW auth (keyring), token-bucket rate limiter
│   │   ├── ingest_daemon.py          # APScheduler loop, 15min per subreddit
│   │   └── post_processor.py        # VADER scoring, LLM escalation dispatch
│   ├── db/
│   │   ├── schema.sql                # All table definitions + indexes
│   │   ├── connection.py             # SQLite connection pool (thread-safe)
│   │   └── queries.py               # All SQL — centralized, no inline SQL elsewhere
│   ├── api/
│   │   ├── schemas.py               # Pydantic request/response models
│   │   └── routes/
│   │       ├── sentiment.py         # /api/sentiment/timeseries, /api/sentiment/compare
│   │       ├── posts.py             # /api/posts/top, /api/posts/:id
│   │       ├── spikes.py            # /api/spikes
│   │       └── config.py            # /api/config/subreddits, /api/config/keywords
│   └── llm/
│       └── escalation.py            # Anthropic API call, structured response parser
├── frontend/
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx                   # Router, top-level state
│       ├── api/
│       │   └── client.js             # Typed fetch wrappers for all endpoints
│       ├── views/
│       │   ├── TimeSeriesView.jsx
│       │   ├── ComparisonView.jsx
│       │   ├── SpikeDetailView.jsx
│       │   └── WordCloudView.jsx
│       └── components/
│           ├── SubredditSelector.jsx
│           ├── TimeRangePicker.jsx
│           └── SentimentBadge.jsx
└── scripts/
    └── seed_subreddits.py            # One-time setup: register tracked subreddits
```

## Data Model

```sql
-- schema.sql

CREATE TABLE subreddits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,        -- "nba", "warriors", "49ers"
    display_name  TEXT,
    tracked       BOOLEAN DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE keywords (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT NOT NULL,
    subreddit_id  INTEGER REFERENCES subreddits(id),
    active        BOOLEAN DEFAULT 1
);

CREATE TABLE posts (
    id              TEXT PRIMARY KEY,           -- Reddit post ID (t3_xxxxx)
    subreddit_id    INTEGER NOT NULL REFERENCES subreddits(id),
    title           TEXT NOT NULL,
    body            TEXT,
    author          TEXT,
    score           INTEGER,
    upvote_ratio    REAL,
    num_comments    INTEGER,
    created_utc     INTEGER NOT NULL,           -- Unix timestamp
    fetched_at      TEXT DEFAULT (datetime('now')),
    vader_compound  REAL,
    vader_pos       REAL,
    vader_neg       REAL,
    vader_neu       REAL,
    llm_sentiment   TEXT,                       -- NULL if not escalated
    llm_confidence  REAL,
    llm_reasoning   TEXT,
    sentiment_source TEXT DEFAULT 'vader'       -- 'vader' | 'llm'
);

CREATE TABLE comments (
    id              TEXT PRIMARY KEY,
    post_id         TEXT NOT NULL REFERENCES posts(id),
    parent_id       TEXT,                       -- NULL = top-level comment
    depth           INTEGER DEFAULT 0,
    body            TEXT NOT NULL,
    author          TEXT,
    score           INTEGER,
    created_utc     INTEGER NOT NULL,
    vader_compound  REAL,
    vader_pos       REAL,
    vader_neg       REAL,
    vader_neu       REAL
);

CREATE TABLE sentiment_buckets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subreddit_id      INTEGER NOT NULL REFERENCES subreddits(id),
    bucket_start      INTEGER NOT NULL,         -- Unix ts, floored to 6h boundary
    avg_compound      REAL,
    post_count        INTEGER,
    comment_count     INTEGER,
    avg_upvote_ratio  REAL,
    spike_flag        BOOLEAN DEFAULT 0,
    computed_at       TEXT DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX idx_posts_subreddit_time ON posts(subreddit_id, created_utc);
CREATE INDEX idx_posts_vader ON posts(vader_compound);
CREATE INDEX idx_comments_post_depth ON comments(post_id, depth);
CREATE INDEX idx_buckets_subreddit_time ON sentiment_buckets(subreddit_id, bucket_start);
CREATE UNIQUE INDEX idx_buckets_unique ON sentiment_buckets(subreddit_id, bucket_start);
```

## API Contracts

### `GET /api/sentiment/timeseries`
```
Query params:
  subreddit    string       required
  start        integer      unix timestamp
  end          integer      unix timestamp
  bucket_size  string       "6h" | "12h" | "1d"  (default: "6h")

Response:
{
  "subreddit": "nba",
  "buckets": [
    {
      "bucket_start": 1710000000,
      "avg_compound": 0.142,
      "post_count": 47,
      "comment_count": 312,
      "avg_upvote_ratio": 0.87,
      "spike_flag": false
    }
  ]
}
```

### `GET /api/sentiment/compare`
```
Query params:
  subreddits   string       comma-separated, e.g. "nba,warriors"
  topic        string       optional keyword filter
  start        integer      unix timestamp
  end          integer      unix timestamp

Response:
{
  "topic": "curry",
  "series": [
    { "subreddit": "nba", "buckets": [...] },
    { "subreddit": "warriors", "buckets": [...] }
  ]
}
```

### `GET /api/posts/top`
```
Query params:
  subreddit    string       required
  start        integer      unix timestamp
  end          integer      unix timestamp
  limit        integer      default 20
  sort         string       "compound" | "score" | "upvote_ratio"

Response:
{
  "posts": [
    {
      "id": "t3_abc123",
      "title": "Post title here",
      "vader_compound": 0.72,
      "score": 4821,
      "upvote_ratio": 0.94,
      "created_utc": 1710001234,
      "sentiment_source": "vader",
      "url": "https://reddit.com/r/nba/comments/abc123/..."
    }
  ]
}
```

### `GET /api/posts/:id`
```
Response: Full post object + top 20 comments sorted by score, with sentiment breakdown
```

### `GET /api/spikes`
```
Query params:
  subreddit        string    required
  lookback_hours   integer   default 24

Response:
{
  "spikes": [
    {
      "bucket_start": 1710000000,
      "delta_compound": 0.41,
      "direction": "positive",
      "top_posts": [ ...post objects ]
    }
  ]
}
```

## Dependencies

```bash
# Backend
pip install praw==7.7.1 vaderSentiment==3.3.2 fastapi==0.111.0 \
    "uvicorn[standard]==0.29.0" anthropic==0.25.0 apscheduler==3.10.4 \
    pydantic==2.7.0 keyring==25.2.0

# Frontend
npm create vite@latest frontend -- --template react
cd frontend && npm install recharts d3
```

## Scope Boundaries

**In scope:**
- PRAW ingestion from targeted subreddits
- VADER sentiment scoring (posts + top-level comments)
- SQLite persistence, 6h bucket aggregation
- FastAPI serving sentiment, post, and spike endpoints
- React dashboard: time-series, comparison, spike drill-down, word cloud
- Optional LLM escalation for ambiguous posts (Phase 3)

**Out of scope (never):**
- Any cloud sync or remote data storage
- Write operations to Reddit (no posting, voting, commenting)
- User authentication on the dashboard (local tool — no auth needed)
- Mobile app

**Deferred (future phases):**
- Comment depth analysis (`depth <= 2`) — Phase 2
- Export to CSV/JSON
- Scheduled email/Slack digest
- Keyword alert notifications

## Security & Credentials

```python
# praw_client.py — credential retrieval pattern
import keyring

client_id     = keyring.get_password("reddit_sentiment", "client_id")
client_secret = keyring.get_password("reddit_sentiment", "client_secret")
anthropic_key = keyring.get_password("reddit_sentiment", "anthropic_key")

# One-time setup (run once from CLI, not from app code)
# keyring.set_password("reddit_sentiment", "client_id", "your_id_here")
```

- No secrets in `.env`, no secrets in config files, no secrets committed to git
- DB file: `~/Library/Application Support/reddit-sentiment/reddit_sentiment.db`
- Only outbound connections: `oauth.reddit.com` and (optionally) `api.anthropic.com`
- PRAW script OAuth2 — token cached in memory by PRAW, not written to disk

---

## Phase 0: Foundation (Week 1)

**Objectives:** PRAW auth wired, SQLite schema deployed, VADER pipeline scoring posts into DB.

**Tasks:**
1. Register Reddit app at developer.reddit.com (script type). Store `client_id`, `client_secret`, `user_agent` in macOS Keychain via `keyring`.
   - **Acceptance:** `python -c "import keyring; print(keyring.get_password('reddit_sentiment', 'client_id'))"` prints the client ID

2. Implement `praw_client.py`: PRAW auth using keyring credentials, token-bucket rate limiter capped at 80 req/min, exponential backoff on 429.
   - **Acceptance:** Fetch 200 posts from r/nba without 429 errors. `reddit.auth.limits` shows requests_remaining > 0 throughout.

3. Implement `schema.sql` and `connection.py`. Deploy schema on first run.
   - **Acceptance:** `python -c "from backend.db.connection import get_db; db = get_db(); db.execute('SELECT 1').fetchone()"` returns `(1,)`

4. Implement `post_processor.py`: VADER score every post (title + body concatenated), score top-level comments. Write all scores to `posts` and `comments` tables.
   - **Acceptance:** `SELECT COUNT(*), ROUND(AVG(vader_compound), 3) FROM posts WHERE subreddit_id=1` returns non-zero count with a plausible average (expect -0.3 to +0.5 for most subreddits)

5. Implement `ingest_daemon.py` with APScheduler. Polls every 15 minutes per tracked subreddit. First-run mode: pulls `.hot()` + `.top(time_filter='week')`. Subsequent runs: `.new()` incremental.
   - **Acceptance:** Daemon runs 30 min. DB row count in `posts` increases each cycle. No uncaught exceptions in log output.

**Phase 0 Verification Checklist:**
- [ ] `python backend/ingest_daemon.py --once --subreddit nba` → posts written to DB
- [ ] `SELECT id, title, vader_compound, upvote_ratio FROM posts LIMIT 5` → all fields populated, compound in [-1, 1]
- [ ] `SELECT COUNT(*) FROM comments WHERE depth=0` → > 0 after one ingest run
- [ ] 60-minute continuous ingest run → no 429 errors, no crashes, DB grows monotonically

**Phase 0 Risks:**
- PRAW's `.new()` returns max ~1000 posts. Mitigate with first-run deep pull. For subreddits with > 1000 daily posts (r/news, r/worldnews), prioritize `.hot()` over `.new()`.

---

## Phase 1: API + Time-Series Frontend (Week 2)

**Objectives:** FastAPI serving data; single-subreddit time-series chart in React; daily usable.

**Tasks:**
1. Implement `sentiment_buckets` aggregation in `queries.py`. Compute 6h buckets from raw `posts` table. Detect spikes: `|current_bucket.avg_compound - prev_bucket.avg_compound| >= 0.3` → `spike_flag=1`.
   - **Acceptance:** `SELECT * FROM sentiment_buckets WHERE spike_flag=1 LIMIT 5` returns rows after reprocessing a week of r/nba data

2. Implement `/api/sentiment/timeseries` FastAPI route with Pydantic response model.
   - **Acceptance:** `curl "localhost:8000/api/sentiment/timeseries?subreddit=nba&start=1710000000&end=1710604800"` returns valid JSON matching schema above

3. Implement `/api/posts/top` and `/api/posts/:id` routes.
   - **Acceptance:** Top posts endpoint returns 20 posts with `vader_compound`, `score`, `upvote_ratio` populated

4. Scaffold React app with Vite. Implement `TimeSeriesView.jsx` using Recharts `LineChart`. Wire to `/api/sentiment/timeseries`.
   - **Acceptance:** Chart renders at localhost:5173 with real data. X-axis: timestamps. Y-axis: compound score (-1 to 1). Spike-flagged buckets show as a distinct color/dot.

5. Add `SubredditSelector.jsx` and `TimeRangePicker.jsx` — drive chart query params.
   - **Acceptance:** Changing subreddit → chart re-fetches and re-renders. Changing time range → bucket count on chart updates.

**Phase 1 Verification Checklist:**
- [ ] `uvicorn backend.main:app --reload` → all routes respond with 200
- [ ] `npm run dev` → chart renders at localhost:5173 with live data
- [ ] Change subreddit in selector → chart updates without page reload
- [ ] Select 7-day range → ~28 buckets visible on chart (7 days × 4 6h-buckets/day)
- [ ] At least one spike visually distinguishable from normal trend points

**Phase 1 Risks:**
- Recharts gaps in sparse data (weekends, low-activity subreddits). Backfill with `null` for missing buckets. Use `connectNulls={false}` on the LineChart.

---

## Phase 2: Drill-Down + Comparison + Word Cloud (Week 3)

**Objectives:** Click-through spike investigation, multi-subreddit comparison, word cloud.

**Tasks:**
1. Build `SpikeDetailView.jsx` — clicking a spike point on the time-series chart opens a slide-in panel. Shows top 10 posts from that 6h window sorted by `|vader_compound|`. Each post shows title, compound score, upvote ratio, direct reddit.com link.
   - **Acceptance:** Click a spike dot → panel opens with posts. Posts are from the correct 6h window. Reddit links are valid.

2. Implement `/api/sentiment/compare` endpoint. Build `ComparisonView.jsx` — two subreddits, same time window, overlaid Recharts lines with distinct colors + legend.
   - **Acceptance:** r/nba vs r/warriors for the same week renders two lines with a legend, x-axes aligned

3. Implement `/api/spikes` endpoint.
   - **Acceptance:** `curl "localhost:8000/api/spikes?subreddit=nba&lookback_hours=48"` returns spike objects with `delta_compound` and `top_posts`

4. Build `WordCloudView.jsx` — D3 word cloud layout. Pull term frequency from post titles in the selected time window via a new `/api/posts/terms` endpoint. Update when time range changes.
   - **Acceptance:** Word cloud renders top 50 terms. Font size scales with frequency. Re-renders within 1s when time range selector changes.

**Phase 2 Verification Checklist:**
- [ ] Click spike on chart → drill-down panel shows ≥ 5 posts from that window
- [ ] Comparison view renders 2 subreddits with aligned x-axes
- [ ] Word cloud renders and updates dynamically
- [ ] `/api/spikes` returns deltas with correct magnitude

---

## Phase 3: LLM Escalation (Week 4 — Optional)

**Objectives:** Route genuinely ambiguous posts (VADER compound near 0) to Claude for deeper analysis.

**Tasks:**
1. Implement `escalation.py`: identify posts where `|vader_compound| < 0.05`, call Anthropic API with structured prompt requesting JSON `{sentiment: "positive|negative|neutral|mixed", confidence: float, reasoning: string}`. Parse and validate response.
   - **Acceptance:** Manual test: submit 10 sarcastic or ambiguous Reddit posts. LLM labels match intuition in ≥ 8/10 cases.

2. Wire into `post_processor.py` behind `config.LLM_ESCALATION_ENABLED` flag. Hard cap: 50 escalations per ingest cycle.
   - **Acceptance:** With flag enabled, `SELECT COUNT(*) FROM posts WHERE sentiment_source='llm'` increases after ingest run. Never exceeds 50/cycle.

3. Surface in `SpikeDetailView.jsx`: posts with `sentiment_source='llm'` show a badge. Hover reveals Claude's one-sentence reasoning.
   - **Acceptance:** LLM-analyzed posts show distinct badge. Hover tooltip shows reasoning text.

**Phase 3 Verification Checklist:**
- [ ] `LLM_ESCALATION_ENABLED=False` → no Anthropic API calls, tool fully functional
- [ ] `LLM_ESCALATION_ENABLED=True` → escalated posts appear with badge in drill-down
- [ ] Escalation count stays ≤ 50/cycle even with large ingests
- [ ] Token cost per 50-post batch ≤ $0.10 (use claude-haiku-4-5 for escalation)

---

## Testing Strategy

**Phase 0:** 1-hour continuous ingest on r/nba. Spot-check 20 rows manually — compound scores should directionally match post content (postgame threads after wins vs losses).

**Phase 1:** `httpie` or `curl` every endpoint. Verify edge cases: empty date range, subreddit with no data in range, single-point time series (should render a dot, not crash).

**Phase 2:** Manually set spike threshold to `0.1` temporarily → verify drill-down fires on low-volatility subreddits. Comparison view: use r/nba vs r/nfl — should show clearly different baselines.

**Phase 3:** Build 20-post fixture with known sentiment ground truth (include sarcasm, irony, mixed sentiment). Verify LLM agreement ≥ 80%. Track actual token cost for one ingest cycle.

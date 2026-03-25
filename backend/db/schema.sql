CREATE TABLE IF NOT EXISTS subreddits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    display_name  TEXT,
    tracked       BOOLEAN DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS keywords (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT NOT NULL,
    subreddit_id  INTEGER REFERENCES subreddits(id),
    active        BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    subreddit_id    INTEGER NOT NULL REFERENCES subreddits(id),
    title           TEXT NOT NULL,
    body            TEXT,
    author          TEXT,
    score           INTEGER,
    upvote_ratio    REAL,
    num_comments    INTEGER,
    created_utc     INTEGER NOT NULL,
    fetched_at      TEXT DEFAULT (datetime('now')),
    vader_compound  REAL,
    vader_pos       REAL,
    vader_neg       REAL,
    vader_neu       REAL,
    llm_sentiment   TEXT,
    llm_confidence  REAL,
    llm_reasoning   TEXT,
    sentiment_source TEXT DEFAULT 'vader'
);

CREATE TABLE IF NOT EXISTS comments (
    id              TEXT PRIMARY KEY,
    post_id         TEXT NOT NULL REFERENCES posts(id),
    parent_id       TEXT,
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

CREATE TABLE IF NOT EXISTS sentiment_buckets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subreddit_id      INTEGER NOT NULL REFERENCES subreddits(id),
    bucket_start      INTEGER NOT NULL,
    avg_compound      REAL,
    post_count        INTEGER,
    comment_count     INTEGER,
    avg_upvote_ratio  REAL,
    spike_flag        BOOLEAN DEFAULT 0,
    computed_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_posts_subreddit_time ON posts(subreddit_id, created_utc);
CREATE INDEX IF NOT EXISTS idx_posts_vader ON posts(vader_compound);
CREATE INDEX IF NOT EXISTS idx_comments_post_depth ON comments(post_id, depth);
CREATE INDEX IF NOT EXISTS idx_buckets_subreddit_time ON sentiment_buckets(subreddit_id, bucket_start);
CREATE UNIQUE INDEX IF NOT EXISTS idx_buckets_unique ON sentiment_buckets(subreddit_id, bucket_start);

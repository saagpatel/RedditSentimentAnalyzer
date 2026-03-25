"""Centralized SQL — all database operations live here. No inline SQL elsewhere."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter


# ---------------------------------------------------------------------------
# Subreddits
# ---------------------------------------------------------------------------

def get_tracked_subreddits(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, display_name FROM subreddits WHERE tracked = 1"
    ).fetchall()


def get_or_create_subreddit(
    conn: sqlite3.Connection,
    name: str,
    display_name: str | None = None,
) -> int:
    """Return the subreddit id, inserting if it doesn't exist."""
    conn.execute(
        "INSERT OR IGNORE INTO subreddits (name, display_name) VALUES (?, ?)",
        (name.lower(), display_name or name),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM subreddits WHERE name = ?", (name.lower(),)
    ).fetchone()
    return row["id"]


def set_subreddit_tracked(
    conn: sqlite3.Connection, subreddit_id: int, tracked: bool
) -> None:
    conn.execute(
        "UPDATE subreddits SET tracked = ? WHERE id = ?",
        (int(tracked), subreddit_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

_POST_COLUMNS = (
    "id", "subreddit_id", "title", "body", "author", "score",
    "upvote_ratio", "num_comments", "created_utc", "vader_compound",
    "vader_pos", "vader_neg", "vader_neu", "llm_sentiment",
    "llm_confidence", "llm_reasoning", "sentiment_source",
)

_POST_UPSERT_SQL = f"""
    INSERT OR REPLACE INTO posts ({', '.join(_POST_COLUMNS)})
    VALUES ({', '.join('?' for _ in _POST_COLUMNS)})
"""


def upsert_post(conn: sqlite3.Connection, post: dict) -> None:
    conn.execute(_POST_UPSERT_SQL, tuple(post[c] for c in _POST_COLUMNS))


def bulk_upsert_posts(conn: sqlite3.Connection, posts: list[dict]) -> int:
    """Batch upsert posts. Returns count inserted/updated."""
    if not posts:
        return 0
    rows = [tuple(p[c] for c in _POST_COLUMNS) for p in posts]
    conn.executemany(_POST_UPSERT_SQL, rows)
    return len(rows)


def post_exists(conn: sqlite3.Connection, post_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM posts WHERE id = ? LIMIT 1", (post_id,)
    ).fetchone()
    return row is not None


def get_latest_post_timestamp(
    conn: sqlite3.Connection, subreddit_id: int
) -> int | None:
    """Return the most recent created_utc for a subreddit, or None if empty."""
    row = conn.execute(
        "SELECT MAX(created_utc) AS latest FROM posts WHERE subreddit_id = ?",
        (subreddit_id,),
    ).fetchone()
    return row["latest"] if row and row["latest"] is not None else None


def get_post_by_id(conn: sqlite3.Connection, post_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()


def get_post_count(conn: sqlite3.Connection, subreddit_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM posts WHERE subreddit_id = ?",
        (subreddit_id,),
    ).fetchone()
    return row["cnt"]


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

_COMMENT_COLUMNS = (
    "id", "post_id", "parent_id", "depth", "body", "author",
    "score", "created_utc", "vader_compound", "vader_pos",
    "vader_neg", "vader_neu",
)

_COMMENT_UPSERT_SQL = f"""
    INSERT OR REPLACE INTO comments ({', '.join(_COMMENT_COLUMNS)})
    VALUES ({', '.join('?' for _ in _COMMENT_COLUMNS)})
"""


def upsert_comment(conn: sqlite3.Connection, comment: dict) -> None:
    conn.execute(
        _COMMENT_UPSERT_SQL, tuple(comment[c] for c in _COMMENT_COLUMNS)
    )


def bulk_upsert_comments(conn: sqlite3.Connection, comments: list[dict]) -> int:
    if not comments:
        return 0
    rows = [tuple(c[col] for col in _COMMENT_COLUMNS) for c in comments]
    conn.executemany(_COMMENT_UPSERT_SQL, rows)
    return len(rows)


def get_comment_count(
    conn: sqlite3.Connection, depth: int | None = None
) -> int:
    if depth is not None:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM comments WHERE depth = ?", (depth,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM comments").fetchone()
    return row["cnt"]


def get_comments_for_post(
    conn: sqlite3.Connection, post_id: str, limit: int = 20
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, body, author, score, created_utc, depth, "
        "vader_compound, vader_pos, vader_neg, vader_neu "
        "FROM comments WHERE post_id = ? ORDER BY score DESC LIMIT ?",
        (post_id, limit),
    ).fetchall()


# ---------------------------------------------------------------------------
# Subreddit lookup
# ---------------------------------------------------------------------------

def get_subreddit_by_name(
    conn: sqlite3.Connection, name: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name, display_name, tracked FROM subreddits WHERE name = ?",
        (name.lower(),),
    ).fetchone()


# ---------------------------------------------------------------------------
# Sentiment Buckets
# ---------------------------------------------------------------------------

_BUCKET_SECONDS = 6 * 3600  # 6 hours


def compute_sentiment_buckets(
    conn: sqlite3.Connection,
    subreddit_id: int,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> int:
    """Aggregate posts into 6h sentiment buckets. Returns count of buckets written.

    Floors created_utc to nearest 6h boundary, computes avg compound/upvote_ratio,
    counts posts and comments per bucket. Uses INSERT OR REPLACE on the unique
    (subreddit_id, bucket_start) constraint.
    """
    where_clauses = ["p.subreddit_id = ?"]
    params: list = [subreddit_id]
    if start_ts is not None:
        where_clauses.append("p.created_utc >= ?")
        params.append(start_ts)
    if end_ts is not None:
        where_clauses.append("p.created_utc < ?")
        params.append(end_ts)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        INSERT OR REPLACE INTO sentiment_buckets
            (subreddit_id, bucket_start, avg_compound, post_count,
             comment_count, avg_upvote_ratio, spike_flag, computed_at)
        SELECT
            p.subreddit_id,
            (p.created_utc / {_BUCKET_SECONDS}) * {_BUCKET_SECONDS} AS bucket_start,
            ROUND(AVG(p.vader_compound), 4),
            COUNT(*),
            COALESCE(SUM(p.num_comments), 0),
            ROUND(AVG(p.upvote_ratio), 4),
            0,
            datetime('now')
        FROM posts p
        WHERE {where_sql}
        GROUP BY p.subreddit_id, bucket_start
    """
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount


def detect_and_flag_spikes(
    conn: sqlite3.Connection,
    subreddit_id: int,
    threshold: float = 0.3,
) -> int:
    """Compare adjacent buckets and set spike_flag where |delta| >= threshold.

    Returns count of buckets flagged.
    """
    # First, reset all spike flags for this subreddit
    conn.execute(
        "UPDATE sentiment_buckets SET spike_flag = 0 WHERE subreddit_id = ?",
        (subreddit_id,),
    )

    # Flag buckets where |current - prior| >= threshold
    sql = """
        UPDATE sentiment_buckets
        SET spike_flag = 1
        WHERE id IN (
            SELECT curr.id
            FROM sentiment_buckets curr
            JOIN sentiment_buckets prev
                ON prev.subreddit_id = curr.subreddit_id
                AND prev.bucket_start = curr.bucket_start - ?
            WHERE curr.subreddit_id = ?
                AND ABS(curr.avg_compound - prev.avg_compound) >= ?
        )
    """
    cursor = conn.execute(sql, (_BUCKET_SECONDS, subreddit_id, threshold))
    conn.commit()
    return cursor.rowcount


def get_sentiment_buckets(
    conn: sqlite3.Connection,
    subreddit_id: int,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> list[sqlite3.Row]:
    """Return ordered sentiment buckets for a subreddit in a time range."""
    where_clauses = ["subreddit_id = ?"]
    params: list = [subreddit_id]
    if start_ts is not None:
        where_clauses.append("bucket_start >= ?")
        params.append(start_ts)
    if end_ts is not None:
        where_clauses.append("bucket_start <= ?")
        params.append(end_ts)

    where_sql = " AND ".join(where_clauses)
    return conn.execute(
        f"SELECT bucket_start, avg_compound, post_count, comment_count, "
        f"avg_upvote_ratio, spike_flag "
        f"FROM sentiment_buckets WHERE {where_sql} ORDER BY bucket_start",
        params,
    ).fetchall()


def get_spikes_in_lookback(
    conn: sqlite3.Connection,
    subreddit_id: int,
    lookback_seconds: int,
) -> list[sqlite3.Row]:
    """Return spike-flagged buckets with delta_compound from prior bucket."""
    import time as _time

    cutoff = int(_time.time()) - lookback_seconds
    return conn.execute(
        """
        SELECT
            curr.bucket_start,
            curr.avg_compound,
            curr.post_count,
            curr.comment_count,
            ROUND(curr.avg_compound - prev.avg_compound, 4) AS delta_compound
        FROM sentiment_buckets curr
        JOIN sentiment_buckets prev
            ON prev.subreddit_id = curr.subreddit_id
            AND prev.bucket_start = curr.bucket_start - ?
        WHERE curr.subreddit_id = ?
            AND curr.spike_flag = 1
            AND curr.bucket_start >= ?
        ORDER BY curr.bucket_start DESC
        """,
        (_BUCKET_SECONDS, subreddit_id, cutoff),
    ).fetchall()


# ---------------------------------------------------------------------------
# Top Posts in Range
# ---------------------------------------------------------------------------

_SORT_COLUMNS = {
    "compound": "vader_compound",
    "score": "score",
    "upvote_ratio": "upvote_ratio",
}


def get_top_posts_in_range(
    conn: sqlite3.Connection,
    subreddit_id: int,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 20,
    sort_by: str = "score",
) -> list[sqlite3.Row]:
    """Return top posts for a subreddit in a time range, sorted by the given column."""
    order_col = _SORT_COLUMNS.get(sort_by, "score")

    where_clauses = ["subreddit_id = ?"]
    params: list = [subreddit_id]
    if start_ts is not None:
        where_clauses.append("created_utc >= ?")
        params.append(start_ts)
    if end_ts is not None:
        where_clauses.append("created_utc < ?")
        params.append(end_ts)

    where_sql = " AND ".join(where_clauses)
    params.append(min(limit, 100))

    return conn.execute(
        f"SELECT id, title, vader_compound, score, upvote_ratio, "
        f"num_comments, created_utc, sentiment_source, "
        f"llm_sentiment, llm_reasoning "
        f"FROM posts WHERE {where_sql} ORDER BY {order_col} DESC LIMIT ?",
        params,
    ).fetchall()


def get_posts_in_bucket(
    conn: sqlite3.Connection,
    subreddit_id: int,
    bucket_start: int,
    limit: int = 5,
) -> list[sqlite3.Row]:
    """Return top posts within a specific 6h bucket window."""
    bucket_end = bucket_start + _BUCKET_SECONDS
    return conn.execute(
        "SELECT id, title, vader_compound, score "
        "FROM posts "
        "WHERE subreddit_id = ? AND created_utc >= ? AND created_utc < ? "
        "ORDER BY ABS(vader_compound) DESC LIMIT ?",
        (subreddit_id, bucket_start, bucket_end, limit),
    ).fetchall()


# ---------------------------------------------------------------------------
# Term Frequency
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it its this that was were be "
    "been being have has had do does did will would shall should can could may "
    "might must am are not no nor so if then than too very just about above "
    "after all also any because before between both by down during each few "
    "from further get got he her here him his how i into me more most my no "
    "only other our out over own same she some such them there these they "
    "those through under until up us we what when where which while who whom "
    "why with you your like don doesn didn won isn aren wasn weren http https "
    "www com reddit removed deleted".split()
)

_WORD_RE = re.compile(r"[a-z]{2,}")


def get_term_frequency(
    conn: sqlite3.Connection,
    subreddit_id: int,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Extract term frequencies from post titles in a time range.

    Returns list of {term, count, avg_compound} sorted by count descending.
    """
    where_clauses = ["subreddit_id = ?"]
    params: list = [subreddit_id]
    if start_ts is not None:
        where_clauses.append("created_utc >= ?")
        params.append(start_ts)
    if end_ts is not None:
        where_clauses.append("created_utc < ?")
        params.append(end_ts)

    where_sql = " AND ".join(where_clauses)
    rows = conn.execute(
        f"SELECT title, vader_compound FROM posts WHERE {where_sql}",
        params,
    ).fetchall()

    if not rows:
        return []

    # Count terms and accumulate compound scores for averaging
    term_counts: Counter[str] = Counter()
    term_compound_sums: dict[str, float] = {}

    for row in rows:
        title = row["title"].lower()
        compound = row["vader_compound"] or 0.0
        tokens = _WORD_RE.findall(title)

        for token in tokens:
            if token in _STOPWORDS:
                continue
            term_counts[token] += 1
            term_compound_sums[token] = term_compound_sums.get(token, 0.0) + compound

    result = []
    for term, count in term_counts.most_common(min(limit, 100)):
        result.append({
            "term": term,
            "count": count,
            "avg_compound": round(term_compound_sums[term] / count, 4),
        })

    return result


# ---------------------------------------------------------------------------
# LLM Escalation Support
# ---------------------------------------------------------------------------

def get_escalation_candidates(
    conn: sqlite3.Connection,
    subreddit_id: int,
    threshold: float = 0.05,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """Return posts eligible for LLM escalation (ambiguous VADER scores)."""
    return conn.execute(
        "SELECT id, title, body, vader_compound "
        "FROM posts "
        "WHERE subreddit_id = ? AND ABS(vader_compound) < ? "
        "AND sentiment_source = 'vader' "
        "ORDER BY ABS(vader_compound) ASC LIMIT ?",
        (subreddit_id, threshold, limit),
    ).fetchall()


def get_llm_escalated_count(
    conn: sqlite3.Connection,
    subreddit_id: int | None = None,
) -> int:
    """Count posts that were escalated to LLM."""
    if subreddit_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM posts "
            "WHERE subreddit_id = ? AND sentiment_source = 'llm'",
            (subreddit_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM posts WHERE sentiment_source = 'llm'"
        ).fetchone()
    return row["cnt"]

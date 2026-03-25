"""Sentiment timeseries and comparison API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import (
    BucketData,
    CompareResponse,
    SeriesEntry,
    TimeseriesResponse,
)
from backend.db import connection as db_conn
from backend.db import queries

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])

_BUCKET_MULTIPLIERS = {"6h": 1, "12h": 2, "1d": 4}


def _buckets_to_response(rows: list, bucket_size: str) -> list[BucketData]:
    """Convert DB rows to BucketData, re-aggregating for larger bucket sizes."""
    if bucket_size == "6h" or not rows:
        return [
            BucketData(
                bucket_start=r["bucket_start"],
                avg_compound=r["avg_compound"],
                post_count=r["post_count"],
                comment_count=r["comment_count"],
                avg_upvote_ratio=r["avg_upvote_ratio"],
                spike_flag=bool(r["spike_flag"]),
            )
            for r in rows
        ]

    # Re-aggregate 6h buckets into larger windows
    multiplier = _BUCKET_MULTIPLIERS[bucket_size]
    window_seconds = 6 * 3600 * multiplier
    groups: dict[int, list] = {}
    for r in rows:
        group_start = (r["bucket_start"] // window_seconds) * window_seconds
        groups.setdefault(group_start, []).append(r)

    result: list[BucketData] = []
    for start in sorted(groups):
        bucket_rows = groups[start]
        total_posts = sum(r["post_count"] for r in bucket_rows)
        total_comments = sum(r["comment_count"] for r in bucket_rows)

        if total_posts > 0:
            weighted_compound = sum(
                (r["avg_compound"] or 0) * r["post_count"] for r in bucket_rows
            ) / total_posts
            weighted_upvote = sum(
                (r["avg_upvote_ratio"] or 0) * r["post_count"] for r in bucket_rows
            ) / total_posts
        else:
            weighted_compound = 0.0
            weighted_upvote = 0.0

        has_spike = any(r["spike_flag"] for r in bucket_rows)

        result.append(
            BucketData(
                bucket_start=start,
                avg_compound=round(weighted_compound, 4),
                post_count=total_posts,
                comment_count=total_comments,
                avg_upvote_ratio=round(weighted_upvote, 4),
                spike_flag=has_spike,
            )
        )
    return result


def _resolve_subreddit(name: str) -> int:
    """Look up subreddit by name, raise 404 if not found."""
    conn = db_conn.get_connection()
    row = queries.get_subreddit_by_name(conn, name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Subreddit '{name}' not found")
    return row["id"]


@router.get("/timeseries", response_model=TimeseriesResponse)
async def get_timeseries(
    subreddit: str = Query(..., description="Subreddit name"),
    start: int | None = Query(None, description="Start unix timestamp"),
    end: int | None = Query(None, description="End unix timestamp"),
    bucket_size: Literal["6h", "12h", "1d"] = Query("6h"),
) -> TimeseriesResponse:
    sub_id = _resolve_subreddit(subreddit)
    conn = db_conn.get_connection()
    rows = queries.get_sentiment_buckets(conn, sub_id, start, end)
    buckets = _buckets_to_response(rows, bucket_size)
    return TimeseriesResponse(subreddit=subreddit, buckets=buckets)


@router.get("/compare", response_model=CompareResponse)
async def get_compare(
    subreddits: str = Query(..., description="Comma-separated subreddit names"),
    start: int | None = Query(None),
    end: int | None = Query(None),
    topic: str | None = Query(None, description="Keyword filter (Phase 2)"),
) -> CompareResponse:
    names = [s.strip() for s in subreddits.split(",") if s.strip()]
    if not names:
        raise HTTPException(status_code=422, detail="At least one subreddit required")

    conn = db_conn.get_connection()
    series: list[SeriesEntry] = []
    for name in names:
        row = queries.get_subreddit_by_name(conn, name)
        if row is None:
            continue  # skip unknown subreddits in comparison
        rows = queries.get_sentiment_buckets(conn, row["id"], start, end)
        buckets = _buckets_to_response(rows, "6h")
        series.append(SeriesEntry(subreddit=name, buckets=buckets))

    return CompareResponse(topic=topic, series=series)

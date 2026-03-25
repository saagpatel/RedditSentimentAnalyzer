"""Spike detection API route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import SpikeData, SpikePostSummary, SpikesResponse
from backend.db import connection as db_conn
from backend.db import queries

router = APIRouter(prefix="/api/spikes", tags=["spikes"])


@router.get("", response_model=SpikesResponse)
async def get_spikes(
    subreddit: str = Query(..., description="Subreddit name"),
    lookback_hours: int = Query(24, ge=1, le=720),
) -> SpikesResponse:
    conn = db_conn.get_connection()
    sub_row = queries.get_subreddit_by_name(conn, subreddit)
    if sub_row is None:
        raise HTTPException(status_code=404, detail=f"Subreddit '{subreddit}' not found")

    sub_id = sub_row["id"]
    lookback_seconds = lookback_hours * 3600

    spike_rows = queries.get_spikes_in_lookback(conn, sub_id, lookback_seconds)

    spikes: list[SpikeData] = []
    for row in spike_rows:
        delta = row["delta_compound"]
        post_rows = queries.get_posts_in_bucket(conn, sub_id, row["bucket_start"])

        top_posts = [
            SpikePostSummary(
                id=p["id"],
                title=p["title"],
                vader_compound=p["vader_compound"],
                score=p["score"],
            )
            for p in post_rows
        ]

        spikes.append(
            SpikeData(
                bucket_start=row["bucket_start"],
                delta_compound=delta,
                direction="positive" if delta > 0 else "negative",
                top_posts=top_posts,
            )
        )

    return SpikesResponse(spikes=spikes)

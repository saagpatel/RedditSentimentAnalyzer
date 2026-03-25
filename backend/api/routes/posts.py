"""Post listing and detail API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.api.schemas import (
    CommentData,
    PostDetailResponse,
    PostSummary,
    TermFrequency,
    TermFrequencyResponse,
    TopPostsResponse,
)
from backend.db import connection as db_conn
from backend.db import queries

router = APIRouter(prefix="/api/posts", tags=["posts"])


def _resolve_subreddit(name: str) -> tuple[int, str]:
    """Return (subreddit_id, subreddit_name) or raise 404."""
    conn = db_conn.get_connection()
    row = queries.get_subreddit_by_name(conn, name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Subreddit '{name}' not found")
    return row["id"], row["name"]


@router.get("/top", response_model=TopPostsResponse)
async def get_top_posts(
    subreddit: str = Query(..., description="Subreddit name"),
    start: int | None = Query(None, description="Start unix timestamp"),
    end: int | None = Query(None, description="End unix timestamp"),
    limit: int = Query(20, ge=1, le=100),
    sort: Literal["compound", "score", "upvote_ratio"] = Query("score"),
) -> TopPostsResponse:
    sub_id, sub_name = _resolve_subreddit(subreddit)
    conn = db_conn.get_connection()
    rows = queries.get_top_posts_in_range(conn, sub_id, start, end, limit, sort)

    posts = [
        PostSummary(
            id=r["id"],
            title=r["title"],
            vader_compound=r["vader_compound"],
            score=r["score"],
            upvote_ratio=r["upvote_ratio"],
            num_comments=r["num_comments"],
            created_utc=r["created_utc"],
            sentiment_source=r["sentiment_source"],
            llm_sentiment=r["llm_sentiment"],
            llm_reasoning=r["llm_reasoning"],
            url=f"https://reddit.com/r/{sub_name}/comments/{r['id']}",
        )
        for r in rows
    ]
    return TopPostsResponse(posts=posts)


@router.get("/terms", response_model=TermFrequencyResponse)
async def get_terms(
    subreddit: str = Query(..., description="Subreddit name"),
    start: int | None = Query(None, description="Start unix timestamp"),
    end: int | None = Query(None, description="End unix timestamp"),
    limit: int = Query(50, ge=1, le=100),
) -> TermFrequencyResponse:
    sub_id, _ = _resolve_subreddit(subreddit)
    conn = db_conn.get_connection()
    terms = queries.get_term_frequency(conn, sub_id, start, end, limit)
    return TermFrequencyResponse(
        subreddit=subreddit,
        terms=[TermFrequency(**t) for t in terms],
    )


@router.get("/{post_id}", response_model=PostDetailResponse)
async def get_post_detail(post_id: str) -> PostDetailResponse:
    conn = db_conn.get_connection()
    post = queries.get_post_by_id(conn, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"Post '{post_id}' not found")

    comment_rows = queries.get_comments_for_post(conn, post_id)
    comments = [
        CommentData(
            id=c["id"],
            body=c["body"],
            author=c["author"],
            score=c["score"],
            created_utc=c["created_utc"],
            depth=c["depth"],
            vader_compound=c["vader_compound"],
        )
        for c in comment_rows
    ]

    return PostDetailResponse(
        id=post["id"],
        title=post["title"],
        body=post["body"],
        author=post["author"],
        score=post["score"],
        upvote_ratio=post["upvote_ratio"],
        num_comments=post["num_comments"],
        created_utc=post["created_utc"],
        vader_compound=post["vader_compound"],
        vader_pos=post["vader_pos"],
        vader_neg=post["vader_neg"],
        vader_neu=post["vader_neu"],
        llm_sentiment=post["llm_sentiment"],
        llm_confidence=post["llm_confidence"],
        llm_reasoning=post["llm_reasoning"],
        sentiment_source=post["sentiment_source"],
        comments=comments,
    )

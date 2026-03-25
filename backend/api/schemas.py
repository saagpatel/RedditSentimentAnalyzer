"""Pydantic response models for all API endpoints."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sentiment Buckets
# ---------------------------------------------------------------------------

class BucketData(BaseModel):
    bucket_start: int
    avg_compound: float | None
    post_count: int
    comment_count: int
    avg_upvote_ratio: float | None
    spike_flag: bool


class TimeseriesResponse(BaseModel):
    subreddit: str
    buckets: list[BucketData]


class SeriesEntry(BaseModel):
    subreddit: str
    buckets: list[BucketData]


class CompareResponse(BaseModel):
    topic: str | None = None
    series: list[SeriesEntry]


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

class PostSummary(BaseModel):
    id: str
    title: str
    vader_compound: float | None
    score: int | None
    upvote_ratio: float | None
    num_comments: int | None
    created_utc: int
    sentiment_source: str | None
    llm_sentiment: str | None = None
    llm_reasoning: str | None = None
    url: str


class TopPostsResponse(BaseModel):
    posts: list[PostSummary]


class CommentData(BaseModel):
    id: str
    body: str
    author: str | None
    score: int | None
    created_utc: int
    depth: int
    vader_compound: float | None


class PostDetailResponse(BaseModel):
    id: str
    title: str
    body: str | None
    author: str | None
    score: int | None
    upvote_ratio: float | None
    num_comments: int | None
    created_utc: int
    vader_compound: float | None
    vader_pos: float | None
    vader_neg: float | None
    vader_neu: float | None
    llm_sentiment: str | None
    llm_confidence: float | None
    llm_reasoning: str | None
    sentiment_source: str | None
    comments: list[CommentData]


# ---------------------------------------------------------------------------
# Spikes
# ---------------------------------------------------------------------------

class SpikePostSummary(BaseModel):
    id: str
    title: str
    vader_compound: float | None
    score: int | None


class SpikeData(BaseModel):
    bucket_start: int
    delta_compound: float
    direction: str
    top_posts: list[SpikePostSummary]


class SpikesResponse(BaseModel):
    spikes: list[SpikeData]


# ---------------------------------------------------------------------------
# Term Frequency
# ---------------------------------------------------------------------------

class TermFrequency(BaseModel):
    term: str
    count: int
    avg_compound: float


class TermFrequencyResponse(BaseModel):
    subreddit: str
    terms: list[TermFrequency]

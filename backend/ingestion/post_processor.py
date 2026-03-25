"""VADER sentiment scoring for Reddit posts and comments."""

from __future__ import annotations

import logging

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()


def score_text(text: str) -> dict[str, float]:
    """Score text with VADER. Returns compound, pos, neg, neu."""
    if not text or not text.strip():
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0}
    scores = _analyzer.polarity_scores(text)
    return {
        "compound": scores["compound"],
        "pos": scores["pos"],
        "neg": scores["neg"],
        "neu": scores["neu"],
    }


def process_submission(submission: object) -> dict:
    """Extract fields from a PRAW Submission and score with VADER.

    Scoring strategy: title + selftext concatenated (period-separated).
    Title carries more signal for link posts where selftext is empty.
    """
    text = submission.title
    if submission.selftext:
        text = f"{submission.title}. {submission.selftext}"

    scores = score_text(text)

    return {
        "id": submission.id,
        "subreddit_id": None,  # filled by caller
        "title": submission.title,
        "body": submission.selftext or None,
        "author": str(submission.author) if submission.author else "[deleted]",
        "score": submission.score,
        "upvote_ratio": submission.upvote_ratio,
        "num_comments": submission.num_comments,
        "created_utc": int(submission.created_utc),
        "vader_compound": scores["compound"],
        "vader_pos": scores["pos"],
        "vader_neg": scores["neg"],
        "vader_neu": scores["neu"],
        "llm_sentiment": None,
        "llm_confidence": None,
        "llm_reasoning": None,
        "sentiment_source": "vader",
    }


def process_comment(comment: object, post_id: str) -> dict | None:
    """Extract fields from a PRAW Comment and score with VADER.

    Phase 0: only top-level comments (parent_id starts with t3_).
    Returns None for non-top-level, deleted, or removed comments.
    """
    is_top_level = comment.parent_id.startswith("t3_")
    if not is_top_level:
        return None

    if not comment.body or comment.body in ("[deleted]", "[removed]"):
        return None

    scores = score_text(comment.body)

    return {
        "id": comment.id,
        "post_id": post_id,
        "parent_id": None,
        "depth": 0,
        "body": comment.body,
        "author": str(comment.author) if comment.author else "[deleted]",
        "score": comment.score,
        "created_utc": int(comment.created_utc),
        "vader_compound": scores["compound"],
        "vader_pos": scores["pos"],
        "vader_neg": scores["neg"],
        "vader_neu": scores["neu"],
    }

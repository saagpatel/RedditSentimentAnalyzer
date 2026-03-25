"""Tests for backend.ingestion.post_processor using fake PRAW objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.ingestion.post_processor import (
    process_comment,
    process_submission,
    score_text,
)


# ---------------------------------------------------------------------------
# Fakes mirroring PRAW attributes
# ---------------------------------------------------------------------------

@dataclass
class FakeSubmission:
    id: str = "t3test1"
    title: str = "Test title"
    selftext: str = "Test body content"
    author: object = "test_author"
    score: int = 100
    upvote_ratio: float = 0.95
    num_comments: int = 10
    created_utc: float = 1710000000.0


@dataclass
class FakeComment:
    id: str = "com1"
    parent_id: str = "t3_t3test1"  # top-level: parent is submission
    body: str = "Great point!"
    author: object = "commenter"
    score: int = 50
    created_utc: float = 1710000100.0


# ---------------------------------------------------------------------------
# score_text
# ---------------------------------------------------------------------------

class TestScoreText:
    def test_positive_text(self):
        scores = score_text("This is absolutely wonderful and amazing!")
        assert scores["compound"] > 0.5
        assert scores["pos"] > 0

    def test_negative_text(self):
        scores = score_text("This is terrible, awful, and disgusting.")
        assert scores["compound"] < -0.5
        assert scores["neg"] > 0

    def test_neutral_text(self):
        scores = score_text("The meeting is at three o'clock.")
        assert abs(scores["compound"]) < 0.3

    def test_empty_string(self):
        scores = score_text("")
        assert scores["compound"] == 0.0
        assert scores["neu"] == 1.0

    def test_none_input(self):
        scores = score_text(None)
        assert scores["compound"] == 0.0

    def test_whitespace_only(self):
        scores = score_text("   \n\t  ")
        assert scores["compound"] == 0.0

    def test_returns_all_keys(self):
        scores = score_text("test")
        assert set(scores.keys()) == {"compound", "pos", "neg", "neu"}


# ---------------------------------------------------------------------------
# process_submission
# ---------------------------------------------------------------------------

class TestProcessSubmission:
    def test_basic_fields(self):
        sub = FakeSubmission()
        result = process_submission(sub)
        assert result["id"] == "t3test1"
        assert result["title"] == "Test title"
        assert result["body"] == "Test body content"
        assert result["author"] == "test_author"
        assert result["score"] == 100
        assert result["created_utc"] == 1710000000
        assert result["sentiment_source"] == "vader"

    def test_vader_scores_populated(self):
        result = process_submission(FakeSubmission())
        assert result["vader_compound"] is not None
        assert -1 <= result["vader_compound"] <= 1
        assert result["vader_pos"] is not None
        assert result["vader_neg"] is not None
        assert result["vader_neu"] is not None

    def test_link_post_no_selftext(self):
        sub = FakeSubmission(selftext="")
        result = process_submission(sub)
        assert result["body"] is None
        # Still gets scored via title
        assert result["vader_compound"] is not None

    def test_deleted_author(self):
        sub = FakeSubmission(author=None)
        result = process_submission(sub)
        assert result["author"] == "[deleted]"

    def test_created_utc_cast_to_int(self):
        sub = FakeSubmission(created_utc=1710000000.5)
        result = process_submission(sub)
        assert isinstance(result["created_utc"], int)

    def test_llm_fields_null(self):
        result = process_submission(FakeSubmission())
        assert result["llm_sentiment"] is None
        assert result["llm_confidence"] is None
        assert result["llm_reasoning"] is None

    def test_subreddit_id_placeholder(self):
        result = process_submission(FakeSubmission())
        assert result["subreddit_id"] is None  # filled by caller


# ---------------------------------------------------------------------------
# process_comment
# ---------------------------------------------------------------------------

class TestProcessComment:
    def test_top_level_comment(self):
        comment = FakeComment()
        result = process_comment(comment, "t3test1")
        assert result is not None
        assert result["id"] == "com1"
        assert result["post_id"] == "t3test1"
        assert result["depth"] == 0
        assert result["parent_id"] is None

    def test_non_top_level_skipped(self):
        comment = FakeComment(parent_id="t1_other_comment")
        result = process_comment(comment, "t3test1")
        assert result is None

    def test_deleted_body_skipped(self):
        comment = FakeComment(body="[deleted]")
        result = process_comment(comment, "t3test1")
        assert result is None

    def test_removed_body_skipped(self):
        comment = FakeComment(body="[removed]")
        result = process_comment(comment, "t3test1")
        assert result is None

    def test_empty_body_skipped(self):
        comment = FakeComment(body="")
        result = process_comment(comment, "t3test1")
        assert result is None

    def test_vader_scores_on_comment(self):
        comment = FakeComment(body="This is absolutely fantastic!")
        result = process_comment(comment, "t3test1")
        assert result["vader_compound"] > 0.3

    def test_deleted_author(self):
        comment = FakeComment(author=None)
        result = process_comment(comment, "t3test1")
        assert result["author"] == "[deleted]"

    def test_created_utc_int(self):
        comment = FakeComment(created_utc=1710000100.9)
        result = process_comment(comment, "t3test1")
        assert isinstance(result["created_utc"], int)

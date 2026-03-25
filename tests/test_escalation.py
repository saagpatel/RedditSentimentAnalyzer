"""Tests for LLM escalation module with mocked Anthropic client."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from backend.config import AppConfig
from backend.llm.escalation import (
    classify_post,
    escalate_ambiguous_posts,
)


# ---------------------------------------------------------------------------
# Fake Anthropic response
# ---------------------------------------------------------------------------

@dataclass
class FakeTextBlock:
    text: str


@dataclass
class FakeMessage:
    content: list = field(default_factory=list)


def _make_mock_client(response_text: str) -> MagicMock:
    client = MagicMock()
    msg = FakeMessage(content=[FakeTextBlock(text=response_text)])
    client.messages.create.return_value = msg
    return client


def _make_post(vader_compound: float = 0.02, title: str = "Test post") -> dict:
    return {
        "id": "test_id",
        "subreddit_id": 1,
        "title": title,
        "body": "Test body",
        "author": "user",
        "score": 100,
        "upvote_ratio": 0.9,
        "num_comments": 5,
        "created_utc": 1710000000,
        "vader_compound": vader_compound,
        "vader_pos": 0.1,
        "vader_neg": 0.1,
        "vader_neu": 0.8,
        "llm_sentiment": None,
        "llm_confidence": None,
        "llm_reasoning": None,
        "sentiment_source": "vader",
    }


def _get_config(enabled: bool = True) -> AppConfig:
    return AppConfig(
        sentiment=AppConfig.model_fields["sentiment"].default.__class__(
            llm_escalation_enabled=enabled,
            llm_escalation_threshold=0.05,
            llm_escalation_cap=50,
        ),
    )


# ---------------------------------------------------------------------------
# classify_post tests
# ---------------------------------------------------------------------------

class TestClassifyPost:
    def test_valid_response(self):
        client = _make_mock_client(
            '{"sentiment": "negative", "confidence": 0.85, "reasoning": "Sarcastic tone"}'
        )
        result = classify_post(client, "Great job team", "Really great...", "nba")
        assert result is not None
        assert result["sentiment"] == "negative"
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "Sarcastic tone"

    def test_mixed_sentiment(self):
        client = _make_mock_client(
            '{"sentiment": "mixed", "confidence": 0.6, "reasoning": "Both praise and criticism"}'
        )
        result = classify_post(client, "Title", None, "nba")
        assert result["sentiment"] == "mixed"

    def test_markdown_wrapped_response(self):
        client = _make_mock_client(
            '```json\n{"sentiment": "positive", "confidence": 0.9, "reasoning": "Happy"}\n```'
        )
        result = classify_post(client, "Title", None, "nba")
        assert result is not None
        assert result["sentiment"] == "positive"

    def test_invalid_sentiment_value(self):
        client = _make_mock_client(
            '{"sentiment": "angry", "confidence": 0.9, "reasoning": "Bad"}'
        )
        result = classify_post(client, "Title", None, "nba")
        assert result is None

    def test_invalid_json(self):
        client = _make_mock_client("This is not JSON")
        result = classify_post(client, "Title", None, "nba")
        assert result is None

    def test_confidence_clamped(self):
        client = _make_mock_client(
            '{"sentiment": "positive", "confidence": 1.5, "reasoning": "Very sure"}'
        )
        result = classify_post(client, "Title", None, "nba")
        assert result["confidence"] == 1.0

    def test_api_error_returns_none(self):
        import anthropic

        client = MagicMock()
        client.messages.create.side_effect = anthropic.APIError(
            message="Rate limited",
            request=MagicMock(),
            body=None,
        )
        result = classify_post(client, "Title", None, "nba")
        assert result is None


# ---------------------------------------------------------------------------
# escalate_ambiguous_posts tests
# ---------------------------------------------------------------------------

class TestEscalateAmbiguousPosts:
    @patch("backend.llm.escalation.get_anthropic_client")
    def test_filters_by_threshold(self, mock_get_client):
        mock_get_client.return_value = _make_mock_client(
            '{"sentiment": "neutral", "confidence": 0.7, "reasoning": "Ambiguous"}'
        )
        config = _get_config(enabled=True)

        posts = [
            _make_post(vader_compound=0.02),   # ambiguous — should escalate
            _make_post(vader_compound=0.5),     # clear positive — skip
            _make_post(vader_compound=-0.8),    # clear negative — skip
        ]
        count = escalate_ambiguous_posts(posts, "nba", config)
        assert count == 1
        assert posts[0]["sentiment_source"] == "llm"
        assert posts[0]["llm_sentiment"] == "neutral"
        assert posts[1]["sentiment_source"] == "vader"
        assert posts[2]["sentiment_source"] == "vader"

    @patch("backend.llm.escalation.get_anthropic_client")
    def test_cap_respected(self, mock_get_client):
        mock_get_client.return_value = _make_mock_client(
            '{"sentiment": "neutral", "confidence": 0.5, "reasoning": "Meh"}'
        )
        config = AppConfig(
            sentiment=AppConfig.model_fields["sentiment"].default.__class__(
                llm_escalation_enabled=True,
                llm_escalation_threshold=0.05,
                llm_escalation_cap=3,
            ),
        )

        posts = [_make_post(vader_compound=0.01) for _ in range(10)]
        count = escalate_ambiguous_posts(posts, "nba", config)
        assert count == 3
        escalated = [p for p in posts if p["sentiment_source"] == "llm"]
        assert len(escalated) == 3

    @patch("backend.llm.escalation.get_anthropic_client")
    def test_no_candidates(self, mock_get_client):
        config = _get_config(enabled=True)
        posts = [_make_post(vader_compound=0.8)]
        count = escalate_ambiguous_posts(posts, "nba", config)
        assert count == 0
        mock_get_client.assert_not_called()

    @patch("backend.llm.escalation.get_anthropic_client")
    def test_partial_failure(self, mock_get_client):
        """If some posts fail classification, others should still succeed."""
        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API error")
            return FakeMessage(
                content=[FakeTextBlock(
                    text='{"sentiment": "positive", "confidence": 0.8, "reasoning": "Good"}'
                )]
            )

        client = MagicMock()
        client.messages.create.side_effect = side_effect
        mock_get_client.return_value = client

        config = _get_config(enabled=True)
        posts = [_make_post(vader_compound=0.01) for _ in range(2)]
        count = escalate_ambiguous_posts(posts, "nba", config)
        # First fails, second succeeds
        assert count == 1

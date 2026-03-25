"""LLM escalation — route ambiguous posts to Claude for deeper sentiment analysis.

Only runs when config.sentiment.llm_escalation_enabled is True.
Credentials come from macOS Keychain via keyring.
"""

from __future__ import annotations

import json
import logging

import anthropic
import keyring

from backend.config import AppConfig

logger = logging.getLogger(__name__)

_VALID_SENTIMENTS = frozenset(("positive", "negative", "neutral", "mixed"))

_SYSTEM_PROMPT = (
    "You are a sentiment classifier for Reddit posts. "
    "Analyze the post's tone, sarcasm, and context. "
    "Return ONLY valid JSON with no markdown formatting."
)

_USER_PROMPT_TEMPLATE = """Classify the sentiment of this Reddit post:

Title: {title}
Body: {body}
Subreddit: r/{subreddit}

Return ONLY this JSON structure:
{{"sentiment": "positive"|"negative"|"neutral"|"mixed", "confidence": 0.0-1.0, "reasoning": "one sentence explaining your classification"}}"""

_client: anthropic.Anthropic | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    """Lazy-init Anthropic client from keyring credentials."""
    global _client
    if _client is not None:
        return _client

    api_key = keyring.get_password("reddit_sentiment", "anthropic_key")
    if not api_key:
        raise RuntimeError(
            "Anthropic API key not found in keyring. "
            "Run: keyring.set_password('reddit_sentiment', 'anthropic_key', '<key>')"
        )

    _client = anthropic.Anthropic(api_key=api_key)
    return _client


def classify_post(
    client: anthropic.Anthropic,
    title: str,
    body: str | None,
    subreddit: str,
) -> dict | None:
    """Classify a single post's sentiment via Claude.

    Returns {sentiment, confidence, reasoning} or None on failure.
    """
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        title=title,
        body=body or "(no body)",
        subreddit=subreddit,
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Handle potential markdown code block wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(text)

        sentiment = result.get("sentiment", "").lower()
        if sentiment not in _VALID_SENTIMENTS:
            logger.warning("Invalid sentiment value: %s", sentiment)
            return None

        confidence = float(result.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        reasoning = str(result.get("reasoning", ""))[:500]

        return {
            "sentiment": sentiment,
            "confidence": round(confidence, 3),
            "reasoning": reasoning,
        }

    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM response as JSON: %s", exc)
        return None
    except anthropic.APIError as exc:
        logger.warning("Anthropic API error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unexpected escalation error: %s", exc)
        return None


def escalate_ambiguous_posts(
    post_records: list[dict],
    subreddit_name: str,
    config: AppConfig,
) -> int:
    """Classify ambiguous posts via LLM and update records in-place.

    Filters posts where |vader_compound| < threshold, caps at escalation_cap,
    calls Claude for each, and updates the post dict with LLM fields.

    Returns count of successfully escalated posts.
    """
    threshold = config.sentiment.llm_escalation_threshold
    cap = config.sentiment.llm_escalation_cap

    candidates = [
        p for p in post_records
        if abs(p.get("vader_compound", 0.0)) < threshold
    ]

    if not candidates:
        logger.info("[%s] No ambiguous posts to escalate", subreddit_name)
        return 0

    # Cap the batch
    batch = candidates[:cap]
    logger.info(
        "[%s] Escalating %d/%d ambiguous posts (threshold=%.2f, cap=%d)",
        subreddit_name, len(batch), len(candidates), threshold, cap,
    )

    client = get_anthropic_client()
    success_count = 0

    for post in batch:
        result = classify_post(
            client,
            post["title"],
            post.get("body"),
            subreddit_name,
        )

        if result is not None:
            post["llm_sentiment"] = result["sentiment"]
            post["llm_confidence"] = result["confidence"]
            post["llm_reasoning"] = result["reasoning"]
            post["sentiment_source"] = "llm"
            success_count += 1

    logger.info(
        "[%s] LLM escalation complete: %d/%d succeeded",
        subreddit_name, success_count, len(batch),
    )
    return success_count

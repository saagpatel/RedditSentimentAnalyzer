"""Ingest daemon — orchestrates PRAW fetching, VADER scoring, and DB writes.

Runs via APScheduler on a 15-minute interval per tracked subreddit.
First run pulls .hot() + .top(week); subsequent runs pull .new() incremental.
"""

from __future__ import annotations

import argparse
import logging
import time

import praw.models
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.config import configure_logging, get_config
from backend.db.connection import deploy_schema, get_connection, get_transaction
from backend.db import queries
from backend.ingestion.praw_client import get_reddit_client, rate_limited_fetch
from backend.ingestion.post_processor import process_comment, process_submission

logger = logging.getLogger(__name__)


def ingest_subreddit(subreddit_name: str) -> None:
    """Run one ingest cycle for a single subreddit."""
    config = get_config()
    conn = get_connection()
    sub_id = queries.get_or_create_subreddit(conn, subreddit_name)
    latest_ts = queries.get_latest_post_timestamp(conn, sub_id)

    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)

    if latest_ts is None:
        logger.info("[%s] First run — pulling hot + top(week)", subreddit_name)
        submissions = _first_run_fetch(subreddit, config)
    else:
        logger.info("[%s] Incremental — pulling new since %d", subreddit_name, latest_ts)
        submissions = _incremental_fetch(subreddit, latest_ts, config)

    if not submissions:
        logger.info("[%s] No new posts found", subreddit_name)
        return

    post_records: list[dict] = []
    comment_records: list[dict] = []

    for submission in submissions:
        post_data = process_submission(submission)
        post_data["subreddit_id"] = sub_id
        post_records.append(post_data)

        try:
            submission.comments.replace_more(limit=0)
            for item in submission.comments.list():
                if not isinstance(item, praw.models.Comment):
                    continue
                comment_data = process_comment(item, submission.id)
                if comment_data is not None:
                    comment_records.append(comment_data)
        except Exception:
            logger.warning(
                "[%s] Failed to fetch comments for post %s — skipping comments",
                subreddit_name, submission.id, exc_info=True,
            )

    # LLM escalation for ambiguous posts (before DB write)
    if config.sentiment.llm_escalation_enabled:
        _run_escalation(post_records, subreddit_name, config)

    with get_transaction() as txn:
        inserted_posts = queries.bulk_upsert_posts(txn, post_records)
        inserted_comments = queries.bulk_upsert_comments(txn, comment_records)

    logger.info(
        "[%s] Ingested %d posts, %d comments",
        subreddit_name, inserted_posts, inserted_comments,
    )

    # Compute sentiment buckets and detect spikes
    _recompute_buckets(conn, sub_id, subreddit_name)


def _run_escalation(
    post_records: list[dict], subreddit_name: str, config: object
) -> None:
    """Run LLM escalation on ambiguous posts. Failures don't block ingest."""
    try:
        from backend.llm.escalation import escalate_ambiguous_posts

        escalate_ambiguous_posts(post_records, subreddit_name, config)
    except Exception:
        logger.error(
            "[%s] LLM escalation failed — continuing without escalation",
            subreddit_name, exc_info=True,
        )


def _recompute_buckets(
    conn: object, sub_id: int, subreddit_name: str
) -> None:
    """Recompute sentiment buckets and flag spikes after ingest."""
    config = get_config()
    try:
        bucket_count = queries.compute_sentiment_buckets(conn, sub_id)
        spike_count = queries.detect_and_flag_spikes(
            conn, sub_id, config.sentiment.spike_threshold
        )
        logger.info(
            "[%s] Computed %d buckets, flagged %d spikes",
            subreddit_name, bucket_count, spike_count,
        )
    except Exception:
        logger.error(
            "[%s] Bucket computation failed", subreddit_name, exc_info=True
        )


def _first_run_fetch(
    subreddit: object, config: object
) -> list:
    """First run: .hot() + .top(week), deduplicated by ID."""
    hot = rate_limited_fetch(
        subreddit.hot(limit=None), config.ingestion.first_run_hot_limit
    )
    top = rate_limited_fetch(
        subreddit.top(time_filter="week", limit=None), config.ingestion.first_run_top_limit
    )

    seen: set[str] = set()
    unique: list = []
    for s in hot + top:
        if s.id not in seen:
            seen.add(s.id)
            unique.append(s)

    logger.info("First-run fetched %d unique posts (%d hot, %d top)", len(unique), len(hot), len(top))
    return unique


def _incremental_fetch(
    subreddit: object, latest_ts: int, config: object
) -> list:
    """Incremental: .new() filtered to posts newer than latest_ts."""
    raw = rate_limited_fetch(
        subreddit.new(limit=None), config.ingestion.incremental_new_limit
    )
    return [s for s in raw if int(s.created_utc) > latest_ts]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def create_scheduler() -> BackgroundScheduler:
    config = get_config()
    scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        }
    )

    for name in config.ingestion.subreddits:
        scheduler.add_job(
            func=ingest_subreddit,
            trigger=IntervalTrigger(minutes=config.ingestion.poll_interval_minutes),
            args=[name],
            id=f"ingest_{name}",
            name=f"Ingest r/{name}",
            replace_existing=True,
        )

    return scheduler


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()
    deploy_schema()

    parser = argparse.ArgumentParser(description="Reddit Sentiment Ingest Daemon")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--subreddit", type=str, help="Override subreddit for --once mode")
    args = parser.parse_args()

    if args.once:
        subreddit = args.subreddit or get_config().ingestion.subreddits[0]
        logger.info("Running single ingest for r/%s", subreddit)
        ingest_subreddit(subreddit)
        logger.info("Done.")
        return

    logger.info("Starting ingest daemon (Ctrl+C to stop)")
    scheduler = create_scheduler()
    scheduler.start()

    # Run first cycle immediately for each subreddit
    for name in get_config().ingestion.subreddits:
        try:
            ingest_subreddit(name)
        except Exception:
            logger.error("Initial ingest failed for r/%s", name, exc_info=True)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler")
        scheduler.shutdown(wait=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Seed the subreddits table with initial tracked subreddits."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import configure_logging
from backend.db.connection import deploy_schema, get_connection
from backend.db import queries

SEED_SUBREDDITS = ["nba", "warriors", "49ers"]


def main() -> None:
    configure_logging()
    deploy_schema()
    conn = get_connection()

    for name in SEED_SUBREDDITS:
        sub_id = queries.get_or_create_subreddit(conn, name, display_name=name)
        print(f"  r/{name} → id={sub_id}")

    tracked = queries.get_tracked_subreddits(conn)
    print(f"\nTracked subreddits: {[r['name'] for r in tracked]}")


if __name__ == "__main__":
    main()

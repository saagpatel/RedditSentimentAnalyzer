#!/usr/bin/env python3
"""One-time setup: store Reddit API credentials in macOS Keychain."""

from __future__ import annotations

import getpass
import sys

import keyring


SERVICE = "reddit_sentiment"


def main() -> None:
    print("Reddit Sentiment Analyzer — Credential Setup")
    print("=" * 50)
    print()
    print("Register a script-type app at https://www.reddit.com/prefs/apps")
    print("Then enter the credentials below.")
    print()

    client_id = input("Client ID: ").strip()
    if not client_id:
        print("Error: client_id is required")
        sys.exit(1)

    client_secret = getpass.getpass("Client Secret: ").strip()
    if not client_secret:
        print("Error: client_secret is required")
        sys.exit(1)

    keyring.set_password(SERVICE, "client_id", client_id)
    keyring.set_password(SERVICE, "client_secret", client_secret)
    print()
    print("Credentials stored in macOS Keychain under service '%s'." % SERVICE)

    # Verify retrieval
    verify_id = keyring.get_password(SERVICE, "client_id")
    verify_secret = keyring.get_password(SERVICE, "client_secret")
    if verify_id == client_id and verify_secret == client_secret:
        print("Verification: OK — credentials retrieved successfully.")
    else:
        print("Verification: FAILED — credentials could not be retrieved.")
        sys.exit(1)

    # Optional: verify PRAW auth
    try:
        import praw

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="reddit-sentiment-analyzer/0.1.0 setup-check",
        )
        reddit.user.me()  # returns None for script apps, but no exception = auth works
        print("PRAW auth: OK — connected to Reddit API.")
    except Exception as exc:
        print(f"PRAW auth: FAILED — {exc}")
        print("Credentials are stored but Reddit API connection failed.")
        print("Check your client_id and client_secret.")
        sys.exit(1)


if __name__ == "__main__":
    main()

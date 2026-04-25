# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Reddit All-Search Scraper
==========================
Search ALL of Reddit (not just specific subreddits) for UPI fraud posts.
"""

import praw
import json
import os
import time
from datetime import datetime
from pathlib import Path

# Queries to search across all Reddit
QUERIES = [
    "UPI fraud India",
    "UPI scam",
    "PhonePe scam",
    "PhonePe fraud",
    "GPay scam India",
    "GPay fraud",
    "Paytm scam",
    "Paytm fraud",
    "OLX QR code scam",
    "OLX UPI fraud",
    "digital arrest scam India",
    "telegram task scam India",
    "job scam UPI India",
    "QR code payment scam India",
    "collect request scam UPI",
    "fake customer care UPI",
    "OTP fraud India UPI",
    "investment scam UPI India",
    "loan app fraud India",
    "BHIM scam",
]

OUTPUT_FILE = Path("data/raw/v2/v2_reddit_500.jsonl")
LLM_DELAY = 1.0


def load_existing_urls():
    """Load URLs from DB and session file."""
    urls = set()

    # Load from DB
    try:
        import psycopg2
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

        conn = psycopg2.connect(
            host="localhost", port="5432", database="securepay",
            user=os.getenv("DB_USER", ""), password=os.getenv("DB_PASSWORD", "")
        )
        cur = conn.cursor()
        cur.execute("SELECT source_post_url FROM scenario_sources WHERE source_post_url IS NOT NULL")
        for row in cur.fetchall():
            if row[0]:
                urls.add(row[0].strip().lower())
        conn.close()
        print(f"[DB] Loaded {len(urls)} URLs")
    except Exception as e:
        print(f"[DB] Warning: {e}")

    # Load from session file
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    url = record.get("source_url", "").lower()
                    if url:
                        urls.add(url)
        print(f"[Session] Total URLs to skip: {len(urls)}")

    return urls


def main():
    # Load env
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    # Init Reddit
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent="SecurePay-AllSearch/3.0"
    )

    # Init Ollama verifier
    from app.scraper.verifier import OllamaFraudVerifier
    verifier = OllamaFraudVerifier()

    # Load existing URLs
    existing_urls = load_existing_urls()

    print("=" * 60)
    print("REDDIT ALL-SEARCH SCRAPER")
    print("=" * 60)
    print(f"Queries: {len(QUERIES)}")
    print(f"URLs to skip: {len(existing_urls)}")
    print("=" * 60)

    saved = 0
    skipped_dup = 0
    skipped_short = 0
    rejected = 0

    try:
        for query in QUERIES:
            print(f"\n[Searching: {query}]")

            # Search ALL of Reddit
            for sort in ["relevance", "new", "top"]:
                results = list(reddit.subreddit("all").search(query, limit=100, sort=sort))

                for post in results:
                    url = f"https://reddit.com{post.permalink}".lower()

                    # Skip duplicates
                    if url in existing_urls:
                        skipped_dup += 1
                        continue

                    # Skip short posts
                    if len(post.selftext) < 100:
                        skipped_short += 1
                        continue

                    # Verify with Ollama
                    time.sleep(LLM_DELAY)
                    result = verifier.verify(post.title, post.selftext)

                    # Must be BOTH fraud AND UPI-related
                    if not (result.get("is_fraud") and result.get("is_upi_related")):
                        rejected += 1
                        continue

                    # Save record
                    record = {
                        "complaint_id": f"reddit_{post.id}",
                        "source_url": f"https://reddit.com{post.permalink}",
                        "source_platform": "reddit",
                        "subreddit": post.subreddit.display_name,
                        "raw_text": post.selftext,
                        "title": post.title,
                        "complainant_name": str(post.author) if post.author else "[deleted]",
                        "date_reported": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d"),
                        "date_scraped": datetime.now().strftime("%Y-%m-%d"),
                        "source_query": query,
                        "is_fraud_verified": True,
                        "is_upi_related": True,
                        "fraud_type": result.get("fraud_type"),
                        "fraud_confidence": result.get("confidence"),
                    }

                    with open(OUTPUT_FILE, "a") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

                    existing_urls.add(url)
                    saved += 1
                    print(f"  + [{result.get('fraud_type')}] r/{post.subreddit}: {post.title[:50]}...")

                    if saved >= 500:  # Target 500 more
                        raise KeyboardInterrupt

    except KeyboardInterrupt:
        pass

    print("\n" + "=" * 60)
    print(f"SAVED: {saved}")
    print(f"Skipped (duplicate): {skipped_dup}")
    print(f"Skipped (short): {skipped_short}")
    print(f"Rejected (not UPI fraud): {rejected}")
    print("=" * 60)


if __name__ == "__main__":
    main()

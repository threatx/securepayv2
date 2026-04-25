# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Reddit scraper for UPI fraud posts.
Uses PRAW (Python Reddit API Wrapper) to search relevant subreddits.
Each post is verified with LLM before being stored.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import praw
from dotenv import load_dotenv

from .verifier import FraudVerifier

load_dotenv()


class RedditScraper:
    """Scrape UPI fraud posts from Reddit with LLM verification."""

    OUTPUT_FILE = Path("data/raw/reddit_upi_fraud.jsonl")
    SCRAPED_IDS_FILE = Path("data/raw/.reddit_scraped_ids.json")

    # Target subreddits for UPI fraud content
    SUBREDDITS = [
        "india",
        "IndianPersonalFinance",
        "LegalAdviceIndia",
        "bangalore",
        "mumbai",
        "delhi",
        "chennai",
        "hyderabad",
        "pune",
        "kolkata",
        # Additional subreddits
        "IndiaInvestments",
        "developersIndia",
        "Scams",
        "CyberSecurityIndia",
        "indiasocial",
        "AskIndia",
        "IndianGaming",
        "IndiaNews",
        "TwoXIndia",
        "IndianEnts",
    ]

    # Search queries to find UPI fraud posts
    SEARCH_QUERIES = [
        "UPI fraud",
        "UPI scam",
        "PhonePe fraud",
        "PhonePe scam",
        "GPay fraud",
        "GPay scam",
        "Google Pay fraud",
        "Google Pay scam",
        "Paytm fraud",
        "Paytm scam",
        "QR code scam",
        "QR code fraud",
        "OLX fraud UPI",
        "OLX scam",
        "money debited scam",
        "collect request scam",
        "fake job UPI",
        "army scam UPI",
        "CISF scam",
        "OTP fraud",
        "UPI PIN stolen",
        # Additional queries
        "lost money UPI",
        "scammed money transfer",
        "bank fraud India",
        "WhatsApp payment scam",
        "Amazon Pay scam",
        "BHIM fraud",
        "BHIM scam",
        "online fraud India",
        "cyber fraud money",
        "loan app scam",
        "instant loan fraud",
        "Quikr scam",
        "Facebook marketplace scam India",
        "Instagram scam India",
        "Telegram scam India",
        "work from home scam India",
        "part time job scam India",
        "task scam India",
        "investment scam India",
        "trading scam India",
        "share market scam India",
    ]

    # Search sort options to get more diverse results
    SEARCH_SORTS = ["relevance", "new", "top", "hot"]

    def __init__(self, verify_with_llm: bool = True):
        """Initialize Reddit scraper with PRAW client."""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "SecurePay/1.0")

        if not client_id or not client_secret:
            raise ValueError(
                "Reddit API credentials not set. Please add to your .env file:\n"
                "REDDIT_CLIENT_ID=your_client_id\n"
                "REDDIT_CLIENT_SECRET=your_client_secret\n"
                "REDDIT_USER_AGENT=SecurePay/1.0\n\n"
                "Create an app at: https://www.reddit.com/prefs/apps"
            )

        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

        self.verify_with_llm = verify_with_llm
        self.verifier = FraudVerifier() if verify_with_llm else None
        self.scraped_ids = self._load_scraped_ids()
        self.stats = {
            "posts_found": 0,
            "posts_skipped_short": 0,
            "posts_skipped_duplicate": 0,
            "posts_rejected_llm": 0,
            "posts_verified": 0,
        }

        # Ensure output directory exists
        self.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_scraped_ids(self) -> set:
        """Load previously scraped post IDs to avoid duplicates."""
        if self.SCRAPED_IDS_FILE.exists():
            with open(self.SCRAPED_IDS_FILE, 'r') as f:
                return set(json.load(f))
        return set()

    def _save_scraped_ids(self):
        """Save scraped post IDs for future runs."""
        self.SCRAPED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.SCRAPED_IDS_FILE, 'w') as f:
            json.dump(list(self.scraped_ids), f)

    def scrape_all(self, limit_per_query: int = 100, target_count: int = None):
        """
        Scrape all configured subreddits with all search queries.

        Args:
            limit_per_query: Max posts to fetch per search query
            target_count: Stop after collecting this many verified posts
        """
        # Count existing verified posts
        existing_count = 0
        if self.OUTPUT_FILE.exists():
            with open(self.OUTPUT_FILE, 'r') as f:
                existing_count = sum(1 for _ in f)

        print("=" * 70)
        print("REDDIT UPI FRAUD SCRAPER")
        print("=" * 70)
        print(f"Subreddits: {len(self.SUBREDDITS)}")
        print(f"Search queries: {len(self.SEARCH_QUERIES)}")
        print(f"Sort options: {len(self.SEARCH_SORTS)}")
        print(f"Limit per query: {limit_per_query}")
        print(f"LLM verification: {'enabled' if self.verify_with_llm else 'disabled'}")
        print(f"Existing records: {existing_count}")
        if target_count:
            print(f"Target total: {target_count} (need {target_count - existing_count} more)")
        print("=" * 70)

        # Adjust target to account for existing records
        adjusted_target = target_count - existing_count if target_count else None

        try:
            for subreddit_name in self.SUBREDDITS:
                print(f"\n{'='*50}")
                print(f"Scraping r/{subreddit_name}")
                print("=" * 50)

                for query in self.SEARCH_QUERIES:
                    for sort in self.SEARCH_SORTS:
                        self._scrape_search(subreddit_name, query, limit_per_query, sort)

                        # Check if we've reached target
                        if adjusted_target and self.stats["posts_verified"] >= adjusted_target:
                            print(f"\nReached target: {target_count} total records")
                            return

                if adjusted_target and self.stats["posts_verified"] >= adjusted_target:
                    break

        finally:
            # Always save progress
            self._save_scraped_ids()
            self._print_summary()

    def _scrape_search(self, subreddit_name: str, query: str, limit: int, sort: str = "relevance"):
        """Search a subreddit for UPI fraud posts."""
        print(f"\n  [{sort}] '{query}'...", end=" ")

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = list(subreddit.search(query, limit=limit, sort=sort))

            new_count = 0
            verified_this_search = 0
            for post in posts:
                self.stats["posts_found"] += 1

                # Skip if already scraped
                if post.id in self.scraped_ids:
                    self.stats["posts_skipped_duplicate"] += 1
                    continue

                new_count += 1

                # Skip short posts (likely not detailed fraud stories)
                if len(post.selftext) < 100:
                    self.stats["posts_skipped_short"] += 1
                    continue

                # Verify with LLM
                if self.verify_with_llm:
                    result = self.verifier.verify(post.title, post.selftext)

                    if not (result["is_fraud"] and result["is_upi_related"]):
                        self.stats["posts_rejected_llm"] += 1
                        # Mark as scraped to avoid re-checking
                        self.scraped_ids.add(post.id)
                        continue

                    print(f"\n    + [{result['fraud_type']}] {post.title[:50]}...")
                    self._save_record(post, result, query)
                    verified_this_search += 1
                else:
                    # No verification - save all
                    self._save_record(post, None, query)
                    verified_this_search += 1

                # Small delay to be nice to Reddit
                time.sleep(0.5)

            # Print summary for this search
            if new_count == 0:
                print(f" ({len(posts)} posts, all duplicates)")
            else:
                print(f" ({len(posts)} posts, {new_count} new, {verified_this_search} verified)")

        except Exception as e:
            print(f" Error: {e}")

    def _save_record(self, post, verification: dict, query: str):
        """Save a verified post to the output file."""
        record = {
            "complaint_id": f"reddit_{post.id}",
            "source_url": f"https://reddit.com{post.permalink}",
            "source_platform": "reddit",
            "subreddit": post.subreddit.display_name,
            "raw_text": post.selftext,
            "title": post.title,
            "complainant_name": str(post.author) if post.author else "[deleted]",
            "complainant_location": None,
            "company_name": None,
            "date_reported": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d"),
            "date_scraped": datetime.now().strftime("%Y-%m-%d"),
            "source_query": query,
            "helpful_yes": post.score,
            "helpful_no": 0,
            "status": None,
            "has_images": self._has_images(post),
            "image_urls": self._get_image_urls(post),
            "is_fraud_verified": verification["is_fraud"] if verification else None,
            "is_upi_related": verification["is_upi_related"] if verification else None,
            "fraud_type": verification["fraud_type"] if verification else None,
            "fraud_confidence": verification["confidence"] if verification else None,
            "post_flair": post.link_flair_text,
            "num_comments": post.num_comments,
        }

        with open(self.OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self.scraped_ids.add(post.id)
        self.stats["posts_verified"] += 1

    def _has_images(self, post) -> bool:
        """Check if post has images."""
        if hasattr(post, 'is_gallery') and post.is_gallery:
            return True
        if post.url:
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            return any(ext in post.url.lower() for ext in image_extensions)
        return False

    def _get_image_urls(self, post) -> list:
        """Extract image URLs from post."""
        urls = []
        try:
            if hasattr(post, 'is_gallery') and post.is_gallery:
                if hasattr(post, 'media_metadata'):
                    for item in post.media_metadata.values():
                        if 's' in item and 'u' in item['s']:
                            urls.append(item['s']['u'])
            elif post.url:
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
                if any(ext in post.url.lower() for ext in image_extensions):
                    urls.append(post.url)
        except Exception:
            pass
        return urls

    def _print_summary(self):
        """Print scraping summary."""
        print("\n" + "=" * 70)
        print("SCRAPING SUMMARY")
        print("=" * 70)
        print(f"Total posts found: {self.stats['posts_found']}")
        print(f"Skipped (too short): {self.stats['posts_skipped_short']}")
        print(f"Skipped (duplicate): {self.stats['posts_skipped_duplicate']}")
        print(f"Rejected by LLM: {self.stats['posts_rejected_llm']}")
        print(f"Verified & saved: {self.stats['posts_verified']}")
        print(f"\nOutput file: {self.OUTPUT_FILE}")
        print("=" * 70)

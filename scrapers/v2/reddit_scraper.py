# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
V2 Reddit Scraper for UPI Fraud Posts
======================================
Expanded subreddits and search queries for deeper coverage.
Outputs to v2_upi_fraud.jsonl
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import praw
from dotenv import load_dotenv

from ..verifier import FraudVerifier
from .config import V2_OUTPUT_FILE, V2_SCRAPED_IDS_FILE, load_existing_urls_from_db

load_dotenv()


class RedditScraperV2:
    """V2 Reddit scraper with expanded coverage. Checks DB for existing URLs."""

    # EXPANDED subreddits - includes city subreddits and more
    SUBREDDITS = [
        # Primary India subreddits
        "india",
        "IndianPersonalFinance",
        "LegalAdviceIndia",
        "IsThisAScamIndia",

        # City subreddits (high local engagement)
        "bangalore",
        "mumbai",
        "delhi",
        "chennai",
        "hyderabad",
        "pune",
        "kolkata",
        "ahmedabad",
        "jaipur",
        "lucknow",

        # Finance and tech subreddits
        "IndiaInvestments",
        "CreditCardsIndia",
        "developersIndia",
        "IndianGaming",

        # Community subreddits
        "indiasocial",
        "AskIndia",
        "TwoXIndia",
        "IndiaNews",
        "IndiaSpeaks",

        # Scam-focused
        "Scams",
        "CyberSecurityIndia",
    ]

    # EXPANDED search queries - more specific patterns
    SEARCH_QUERIES = [
        # Core UPI fraud queries
        "UPI fraud",
        "UPI scam",
        "UPI hack",
        "UPI money lost",

        # App-specific
        "PhonePe fraud",
        "PhonePe scam",
        "PhonePe money stolen",
        "GPay fraud",
        "GPay scam",
        "GPay money lost",
        "Google Pay fraud",
        "Google Pay scam",
        "Paytm fraud",
        "Paytm scam",
        "Paytm UPI",
        "BHIM fraud",
        "BHIM scam",
        "CRED fraud",
        "Amazon Pay fraud",

        # Scam patterns
        "QR code scam",
        "QR code fraud",
        "collect request scam",
        "collect request fraud",
        "OTP fraud",
        "OTP scam",
        "fake customer care",
        "fake helpline",

        # Platform-specific scams
        "OLX fraud",
        "OLX scam",
        "OLX UPI",
        "Quikr scam",
        "Facebook marketplace scam",
        "Instagram scam money",
        "WhatsApp scam money",
        "Telegram scam money",

        # Job/task scams
        "task fraud telegram",
        "task scam UPI",
        "part time job scam",
        "work from home scam",
        "data entry scam",
        "youtube like scam",
        "video watching scam",

        # Investment scams
        "investment scam UPI",
        "trading scam",
        "stock market fraud",
        "crypto scam UPI",
        "money doubling scam",

        # Loan scams
        "loan app scam",
        "instant loan fraud",
        "loan app harassment",
        "loan app blackmail",

        # Impersonation
        "army fraud UPI",
        "CISF scam",
        "police impersonation fraud",
        "bank executive fraud",
        "RBI fraud call",

        # Specific incident patterns
        "money debited fraud",
        "account frozen fraud",
        "refund scam",
        "KYC fraud",
        "Aadhaar link fraud",

        # Cyber crime
        "cyber crime money",
        "cyber fraud complaint",
        "1930 helpline",
        "money recovered fraud",

        # Remote access
        "AnyDesk fraud",
        "TeamViewer scam",
        "screen share fraud",
    ]

    # Sort options for diverse results
    SEARCH_SORTS = ["relevance", "new", "top", "hot"]

    def __init__(self, verify_with_llm: bool = True):
        """Initialize Reddit scraper with PRAW client."""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "SecurePay/2.0")

        if not client_id or not client_secret:
            raise ValueError(
                "Reddit API credentials not set. Add to .env:\n"
                "REDDIT_CLIENT_ID=your_client_id\n"
                "REDDIT_CLIENT_SECRET=your_client_secret"
            )

        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

        self.verify_with_llm = verify_with_llm
        self.verifier = FraudVerifier() if verify_with_llm else None
        self.scraped_ids = self._load_scraped_ids()

        # Load existing URLs from database to avoid duplicates
        self.existing_db_urls = load_existing_urls_from_db()

        self.stats = {
            "posts_found": 0,
            "posts_skipped_short": 0,
            "posts_skipped_duplicate": 0,
            "posts_skipped_in_db": 0,
            "posts_rejected_llm": 0,
            "posts_verified": 0,
        }

        V2_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_scraped_ids(self) -> set:
        """Load previously scraped post IDs."""
        ids = set()

        # Load from tracking file
        if V2_SCRAPED_IDS_FILE.exists():
            with open(V2_SCRAPED_IDS_FILE, 'r') as f:
                data = json.load(f)
                ids.update(data.get('reddit', []))

        # Also load from output file
        if V2_OUTPUT_FILE.exists():
            with open(V2_OUTPUT_FILE, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if record.get('source_platform') == 'reddit':
                            # Extract reddit ID from complaint_id
                            cid = record.get('complaint_id', '')
                            if cid.startswith('reddit_'):
                                ids.add(cid.replace('reddit_', ''))

        return ids

    def _save_scraped_ids(self):
        """Save scraped IDs to tracking file."""
        existing = {}
        if V2_SCRAPED_IDS_FILE.exists():
            with open(V2_SCRAPED_IDS_FILE, 'r') as f:
                existing = json.load(f)

        existing['reddit'] = list(self.scraped_ids)

        with open(V2_SCRAPED_IDS_FILE, 'w') as f:
            json.dump(existing, f)

    def scrape_all(self, limit_per_query: int = 100, target_count: int = 300):
        """
        Scrape all configured subreddits with all search queries.

        Args:
            limit_per_query: Max posts per search query
            target_count: Stop after this many verified posts
        """
        existing_count = self._count_existing_reddit_records()

        print("=" * 70)
        print("V2 REDDIT UPI FRAUD SCRAPER")
        print("=" * 70)
        print(f"Subreddits: {len(self.SUBREDDITS)}")
        print(f"Search queries: {len(self.SEARCH_QUERIES)}")
        print(f"Sort options: {len(self.SEARCH_SORTS)}")
        print(f"Limit per query: {limit_per_query}")
        print(f"LLM verification: {'enabled' if self.verify_with_llm else 'disabled'}")
        print(f"Existing Reddit records in v2: {existing_count}")
        print(f"Target new records: {target_count}")
        print(f"Output: {V2_OUTPUT_FILE}")
        print("=" * 70)

        try:
            for subreddit_name in self.SUBREDDITS:
                print(f"\n{'='*50}")
                print(f"Scraping r/{subreddit_name}")
                print("=" * 50)

                for query in self.SEARCH_QUERIES:
                    for sort in self.SEARCH_SORTS:
                        self._scrape_search(subreddit_name, query, limit_per_query, sort)

                        if self.stats["posts_verified"] >= target_count:
                            print(f"\nReached target: {target_count} new records")
                            return

                if self.stats["posts_verified"] >= target_count:
                    break

        finally:
            self._save_scraped_ids()
            self._print_summary()

    def _count_existing_reddit_records(self) -> int:
        """Count existing Reddit records in v2 output file."""
        count = 0
        if V2_OUTPUT_FILE.exists():
            with open(V2_OUTPUT_FILE, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if record.get('source_platform') == 'reddit':
                            count += 1
        return count

    def _scrape_search(self, subreddit_name: str, query: str, limit: int, sort: str):
        """Search a subreddit for UPI fraud posts."""
        print(f"\n  [{sort}] '{query}'...", end=" ")

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = list(subreddit.search(query, limit=limit, sort=sort))

            new_count = 0
            verified_this_search = 0

            for post in posts:
                self.stats["posts_found"] += 1

                if post.id in self.scraped_ids:
                    self.stats["posts_skipped_duplicate"] += 1
                    continue

                # Check if URL already exists in database
                post_url = f"https://reddit.com{post.permalink}".lower()
                if post_url in self.existing_db_urls:
                    self.stats["posts_skipped_in_db"] += 1
                    self.scraped_ids.add(post.id)  # Mark as scraped to skip in future
                    continue

                new_count += 1

                if len(post.selftext) < 100:
                    self.stats["posts_skipped_short"] += 1
                    continue

                if self.verify_with_llm:
                    result = self.verifier.verify(post.title, post.selftext)

                    if not (result["is_fraud"] and result["is_upi_related"]):
                        self.stats["posts_rejected_llm"] += 1
                        self.scraped_ids.add(post.id)
                        continue

                    print(f"\n    + [{result['fraud_type']}] {post.title[:50]}...")
                    self._save_record(post, result, query)
                    verified_this_search += 1
                else:
                    self._save_record(post, None, query)
                    verified_this_search += 1

                time.sleep(0.5)

            if new_count == 0:
                print(f" ({len(posts)} posts, all duplicates)")
            else:
                print(f" ({len(posts)} posts, {new_count} new, {verified_this_search} verified)")

        except Exception as e:
            print(f" Error: {e}")

    def _save_record(self, post, verification: dict, query: str):
        """Save a verified post to v2 output file."""
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

        with open(V2_OUTPUT_FILE, 'a', encoding='utf-8') as f:
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
        print("V2 REDDIT SCRAPING SUMMARY")
        print("=" * 70)
        print(f"Total posts found: {self.stats['posts_found']}")
        print(f"Skipped (too short): {self.stats['posts_skipped_short']}")
        print(f"Skipped (duplicate in v2): {self.stats['posts_skipped_duplicate']}")
        print(f"Skipped (already in DB): {self.stats['posts_skipped_in_db']}")
        print(f"Rejected by LLM: {self.stats['posts_rejected_llm']}")
        print(f"Verified & saved: {self.stats['posts_verified']}")
        print(f"\nOutput file: {V2_OUTPUT_FILE}")
        print("=" * 70)


if __name__ == "__main__":
    scraper = RedditScraperV2(verify_with_llm=True)
    scraper.scrape_all(target_count=300)

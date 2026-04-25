# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Google News scraper for UPI fraud articles.
Searches Google News for UPI fraud related articles and extracts full content.
Each article is verified with LLM before being stored.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from gnews import GNews
from dotenv import load_dotenv

from .verifier import FraudVerifier

load_dotenv()


class GoogleNewsScraper:
    """Scrape UPI fraud articles from Google News with LLM verification."""

    OUTPUT_FILE = Path("data/raw/google_news_upi_fraud.jsonl")
    SCRAPED_IDS_FILE = Path("data/raw/.google_news_scraped_ids.json")

    # Search queries to find UPI fraud articles
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
        "OLX fraud",
        "OLX scam",
        "digital payment fraud",
        "online payment scam",
        "UPI PIN fraud",
        "OTP fraud",
        "loan app fraud",
        "instant loan scam",
        "cyber fraud India",
        "WhatsApp payment scam",
        "Amazon Pay fraud",
        "BHIM fraud",
        "BHIM scam",
        "mobile payment fraud",
        "digital wallet scam",
        "bank fraud India",
        "money transfer scam",
        "investment scam India",
        "trading scam India",
        "task fraud",
        "part time job scam",
        "work from home scam",
        "arrested UPI fraud",
        "police UPI scam",
        "cyber cell fraud",
    ]

    def __init__(self, verify_with_llm: bool = True):
        """Initialize Google News scraper."""
        self.gnews = GNews(language='en', country='IN', max_results=100)

        self.verify_with_llm = verify_with_llm
        self.verifier = FraudVerifier() if verify_with_llm else None
        self.scraped_ids = self._load_scraped_ids()
        self.stats = {
            "articles_found": 0,
            "articles_skipped_short": 0,
            "articles_skipped_duplicate": 0,
            "articles_rejected_llm": 0,
            "articles_verified": 0,
        }

        # Ensure output directory exists
        self.OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_scraped_ids(self) -> set:
        """Load previously scraped article IDs to avoid duplicates."""
        if self.SCRAPED_IDS_FILE.exists():
            with open(self.SCRAPED_IDS_FILE, 'r') as f:
                return set(json.load(f))
        return set()

    def _save_scraped_ids(self):
        """Save scraped article IDs for future runs."""
        self.SCRAPED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.SCRAPED_IDS_FILE, 'w') as f:
            json.dump(list(self.scraped_ids), f)

    def _generate_article_id(self, article: dict) -> str:
        """Generate a unique ID for an article based on title and URL."""
        import hashlib
        unique_str = f"{article.get('title', '')}{article.get('url', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]

    def scrape_all(self, target_count: int = 200):
        """
        Search Google News for UPI fraud articles.

        Args:
            target_count: Stop after collecting this many verified articles
        """
        # Count existing verified articles
        existing_count = 0
        if self.OUTPUT_FILE.exists():
            with open(self.OUTPUT_FILE, 'r') as f:
                existing_count = sum(1 for _ in f)

        print("=" * 70)
        print("GOOGLE NEWS UPI FRAUD SCRAPER")
        print("=" * 70)
        print(f"Search queries: {len(self.SEARCH_QUERIES)}")
        print(f"LLM verification: {'enabled' if self.verify_with_llm else 'disabled'}")
        print(f"Existing records: {existing_count}")
        print(f"Target total: {target_count} (need {target_count - existing_count} more)")
        print("=" * 70)

        # Adjust target to account for existing records
        adjusted_target = target_count - existing_count

        if adjusted_target <= 0:
            print(f"\nAlready have {existing_count} records. Target reached!")
            return

        try:
            for query in self.SEARCH_QUERIES:
                self._search_news(query)

                # Check if we've reached target
                if self.stats["articles_verified"] >= adjusted_target:
                    print(f"\nReached target: {target_count} total records")
                    break

                # Save progress periodically
                if self.stats["articles_verified"] % 10 == 0:
                    self._save_scraped_ids()

        finally:
            # Always save progress
            self._save_scraped_ids()
            self._print_summary()

    def _search_news(self, query: str):
        """Search Google News for UPI fraud articles."""
        print(f"\nSearching: '{query}'...", end=" ", flush=True)

        try:
            results = self.gnews.get_news(query)

            if not results:
                print("(no results)")
                return

            new_count = 0
            verified_this_search = 0

            for article in results:
                self.stats["articles_found"] += 1

                # Generate unique ID
                article_id = self._generate_article_id(article)

                # Skip if already scraped
                if article_id in self.scraped_ids:
                    self.stats["articles_skipped_duplicate"] += 1
                    continue

                new_count += 1

                title = article.get('title', '')
                description = article.get('description', '')
                full_text = f"{title}. {description}"

                # Skip short articles
                if len(full_text) < 50:
                    self.stats["articles_skipped_short"] += 1
                    self.scraped_ids.add(article_id)
                    continue

                # Verify with LLM
                if self.verify_with_llm:
                    result = self.verifier.verify(title, description)

                    if not (result["is_fraud"] and result["is_upi_related"]):
                        self.stats["articles_rejected_llm"] += 1
                        self.scraped_ids.add(article_id)
                        continue

                    print(f"\n    + [{result['fraud_type']}] {title[:60]}...")
                    self._save_record(article, article_id, result, query)
                    verified_this_search += 1
                else:
                    self._save_record(article, article_id, None, query)
                    verified_this_search += 1

                # Small delay
                time.sleep(0.3)

            # Print summary for this search
            if new_count == 0:
                print(f"({len(results)} articles, all duplicates)")
            else:
                print(f"({len(results)} articles, {new_count} new, {verified_this_search} verified)")

            # Delay between searches
            time.sleep(2)

        except Exception as e:
            print(f"Error: {e}")

    def _save_record(self, article: dict, article_id: str, verification: dict, query: str):
        """Save a verified article to the output file."""
        # Parse date
        date_str = article.get('published date', '')
        try:
            if date_str:
                from dateparser import parse
                parsed_date = parse(date_str)
                date_reported = parsed_date.strftime("%Y-%m-%d") if parsed_date else None
            else:
                date_reported = None
        except:
            date_reported = None

        record = {
            "complaint_id": f"gnews_{article_id}",
            "source_url": article.get('url', ''),
            "source_platform": "google_news",
            "news_source": article.get('publisher', {}).get('title', '') if isinstance(article.get('publisher'), dict) else str(article.get('publisher', '')),
            "raw_text": article.get('description', ''),
            "title": article.get('title', ''),
            "complainant_name": None,
            "complainant_location": None,
            "company_name": None,
            "date_reported": date_reported,
            "date_scraped": datetime.now().strftime("%Y-%m-%d"),
            "source_query": query,
            "helpful_yes": 0,
            "helpful_no": 0,
            "status": None,
            "has_images": False,
            "image_urls": [],
            "is_fraud_verified": verification["is_fraud"] if verification else None,
            "is_upi_related": verification["is_upi_related"] if verification else None,
            "fraud_type": verification["fraud_type"] if verification else None,
            "fraud_confidence": verification["confidence"] if verification else None,
        }

        with open(self.OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self.scraped_ids.add(article_id)
        self.stats["articles_verified"] += 1

    def _print_summary(self):
        """Print scraping summary."""
        print("\n" + "=" * 70)
        print("SCRAPING SUMMARY")
        print("=" * 70)
        print(f"Total articles found: {self.stats['articles_found']}")
        print(f"Skipped (too short): {self.stats['articles_skipped_short']}")
        print(f"Skipped (duplicate): {self.stats['articles_skipped_duplicate']}")
        print(f"Rejected by LLM: {self.stats['articles_rejected_llm']}")
        print(f"Verified & saved: {self.stats['articles_verified']}")
        print(f"\nOutput file: {self.OUTPUT_FILE}")
        print("=" * 70)


if __name__ == "__main__":
    scraper = GoogleNewsScraper(verify_with_llm=True)
    scraper.scrape_all(target_count=200)

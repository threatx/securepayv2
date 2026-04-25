# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Google Play Store UPI App Review Scraper

Scrapes 1-2 star reviews from UPI apps (GPay, PhonePe, Paytm, BHIM)
and filters for fraud/scam related complaints.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google_play_scraper import Sort, reviews_all, reviews

# Load environment variables from .env file
load_dotenv()

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.scraper.verifier import FraudVerifier


class PlayStoreScraper:
    """Scrape UPI app reviews from Google Play Store for fraud detection."""

    # Target UPI apps with their package IDs
    UPI_APPS = {
        "GPay": "com.google.android.apps.nbu.paisa.user",
        "PhonePe": "com.phonepe.app",
        "Paytm": "net.one97.paytm",
        "BHIM": "in.org.npci.upiapp",
    }

    # Fraud-related keywords (English and Hindi transliterations)
    FRAUD_KEYWORDS = [
        # English keywords
        "scam", "fraud", "fraudster", "cheat", "cheated", "cheating",
        "stolen", "steal", "stole", "hack", "hacked", "hacker",
        "unauthorized", "unauthorised", "without permission",
        "money deducted", "amount deducted", "deducted without",
        "not received", "didn't receive", "did not receive",
        "fake", "phishing", "otp", "lost money", "money lost",
        "scammer", "fraudulent", "illegal", "criminal",
        "customer care fraud", "fake customer care",
        "qr code", "qr scam", "scan and pay",
        "collect request", "payment request",
        "job offer", "job scam", "lottery", "reward scam",
        "remote access", "anydesk", "teamviewer",
        "sim swap", "sim block",
        # Hindi transliterations
        "dhoka", "thug", "thugs", "loot", "looted", "lut",
        "paisa kata", "paise kate", "paise gaye",
        "fraud ho gaya", "scam ho gaya",
        "bewakoof", "chori",
    ]

    def __init__(self, output_file: str = "data/raw/playstore_upi_fraud.jsonl",
                 use_verification: bool = True, lang: str = "en", sort_order: str = "newest"):
        """
        Initialize the scraper.

        Args:
            output_file: Path to output JSONL file
            use_verification: Whether to use LLM verification
            lang: Language code for reviews (en, hi, etc.)
            sort_order: Sort order (newest, relevant)
        """
        self.lang = lang
        self.sort_order = Sort.NEWEST if sort_order == "newest" else Sort.MOST_RELEVANT
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Track scraped review IDs to avoid duplicates
        self.scraped_ids_file = self.output_file.parent / ".playstore_scraped_ids.json"
        self.scraped_ids = self._load_scraped_ids()

        # LLM verifier
        self.use_verification = use_verification
        self.verifier = None
        if use_verification:
            try:
                self.verifier = FraudVerifier()
                print("LLM verification enabled (Groq API)")
            except ValueError as e:
                print(f"Warning: {e}")
                print("Continuing without LLM verification...")
                self.use_verification = False

        # Stats
        self.stats = {
            "total_reviews_fetched": 0,
            "fraud_keyword_matches": 0,
            "llm_verified_fraud": 0,
            "llm_verified_upi": 0,
            "saved_records": 0,
        }

    def _load_scraped_ids(self) -> set:
        """Load previously scraped review IDs."""
        if self.scraped_ids_file.exists():
            with open(self.scraped_ids_file, "r") as f:
                return set(json.load(f))
        return set()

    def _save_scraped_ids(self):
        """Save scraped review IDs."""
        with open(self.scraped_ids_file, "w") as f:
            json.dump(list(self.scraped_ids), f)

    def _contains_fraud_keyword(self, text: str) -> bool:
        """Check if text contains any fraud-related keywords."""
        if not text:
            return False
        text_lower = text.lower()
        for keyword in self.FRAUD_KEYWORDS:
            if keyword in text_lower:
                return True
        return False

    def _extract_upi_id(self, text: str) -> Optional[str]:
        """Extract UPI ID from text if present."""
        # UPI ID pattern: username@provider
        upi_pattern = r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9]+\b'
        matches = re.findall(upi_pattern, text)
        # Filter out email-like patterns
        upi_matches = [m for m in matches if not any(
            domain in m.lower() for domain in ['gmail', 'yahoo', 'hotmail', 'outlook', 'mail']
        )]
        return upi_matches[0] if upi_matches else None

    def _extract_amount(self, text: str) -> Optional[str]:
        """Extract monetary amount from text if present."""
        # Pattern for Indian Rupees
        patterns = [
            r'₹\s*[\d,]+(?:\.\d{2})?',  # ₹1000 or ₹1,000.00
            r'Rs\.?\s*[\d,]+(?:\.\d{2})?',  # Rs.1000 or Rs 1000
            r'INR\s*[\d,]+(?:\.\d{2})?',  # INR 1000
            r'(?:rupees?|rs)\s*[\d,]+',  # rupees 1000
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None

    def _format_record(self, review: dict, app_name: str,
                       verification: Optional[dict] = None) -> dict:
        """Format review data to match existing JSONL schema."""
        review_id = review.get("reviewId", "")

        record = {
            "complaint_id": f"playstore_{app_name.lower()}_{review_id}",
            "source_url": f"https://play.google.com/store/apps/details?id={self.UPI_APPS[app_name]}&reviewId={review_id}",
            "raw_text": review.get("content", ""),
            "title": f"{app_name} Review - {review.get('score', 0)} star",
            "complainant_name": review.get("userName", "Anonymous"),
            "complainant_location": None,  # Not available in Play Store reviews
            "company_name": app_name,
            "date_reported": review.get("at", datetime.now()).isoformat() if review.get("at") else datetime.now().isoformat(),
            "date_scraped": datetime.now().isoformat(),
            "source_query": f"playstore_{app_name.lower()}",
            "helpful_yes": review.get("thumbsUpCount", 0),
            "helpful_no": 0,  # Not available
            "status": None,
            "has_images": False,  # Not available in basic review data
            "image_urls": [],
            "rating": review.get("score", 0),
            "app_version": review.get("reviewCreatedVersion", ""),
            "reply_content": review.get("replyContent", ""),
            "reply_date": review.get("repliedAt", "").isoformat() if review.get("repliedAt") else None,
        }

        # Add extracted entities
        record["extracted_upi_id"] = self._extract_upi_id(record["raw_text"])
        record["extracted_amount"] = self._extract_amount(record["raw_text"])

        # Add verification results
        if verification:
            record["is_fraud_verified"] = verification.get("is_fraud", False)
            record["is_upi_related"] = verification.get("is_upi_related", False)
            record["fraud_type"] = verification.get("fraud_type")
            record["fraud_confidence"] = verification.get("confidence", "low")
            record["verification_reason"] = verification.get("reason", "")
        else:
            record["is_fraud_verified"] = True  # Assumed if no verification
            record["is_upi_related"] = True
            record["fraud_type"] = "unknown"
            record["fraud_confidence"] = "low"
            record["verification_reason"] = "No LLM verification"

        return record

    def _save_record(self, record: dict):
        """Append record to JSONL file."""
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.stats["saved_records"] += 1

    def scrape_app_reviews(self, app_name: str, max_reviews: int = 500,
                           target_fraud_count: int = 25) -> int:
        """
        Scrape reviews from a specific app.

        Args:
            app_name: Name of the app (must be in UPI_APPS)
            max_reviews: Maximum reviews to fetch
            target_fraud_count: Stop after finding this many fraud cases

        Returns:
            Number of fraud records found
        """
        if app_name not in self.UPI_APPS:
            raise ValueError(f"Unknown app: {app_name}")

        app_id = self.UPI_APPS[app_name]
        print(f"\n{'='*60}")
        print(f"Scraping {app_name} ({app_id})")
        print(f"Target: {target_fraud_count} fraud records")
        print(f"{'='*60}")

        fraud_count = 0
        reviews_processed = 0

        try:
            # Fetch reviews - sorted by newest, focusing on low ratings
            print(f"Fetching reviews (1-2 stars, newest first)...")

            all_reviews = []

            # Fetch low-star reviews with pagination
            for star_rating in [1, 2, 3]:
                continuation_token = None
                fetched_for_rating = 0
                max_per_rating = max_reviews // 3

                while fetched_for_rating < max_per_rating:
                    batch_size = min(200, max_per_rating - fetched_for_rating)
                    result, continuation_token = reviews(
                        app_id,
                        lang=self.lang,
                        country='in',
                        sort=self.sort_order,
                        count=batch_size,
                        filter_score_with=star_rating,
                        continuation_token=continuation_token
                    )

                    if not result:
                        break

                    all_reviews.extend(result)
                    fetched_for_rating += len(result)
                    print(f"  Fetched {len(result)} {star_rating}-star reviews (total: {len(all_reviews)})")

                    if continuation_token is None:
                        break

            print(f"Total fetched: {len(all_reviews)} reviews (1-2 stars)")
            self.stats["total_reviews_fetched"] += len(all_reviews)

            for review in all_reviews:
                if fraud_count >= target_fraud_count:
                    print(f"\nReached target of {target_fraud_count} fraud records!")
                    break

                review_id = review.get("reviewId", "")

                # Skip if already scraped
                if review_id in self.scraped_ids:
                    continue

                reviews_processed += 1
                content = review.get("content", "")

                # First filter: keyword matching
                if not self._contains_fraud_keyword(content):
                    continue

                self.stats["fraud_keyword_matches"] += 1
                print(f"\n[{reviews_processed}] Found keyword match in review...")
                print(f"   Preview: {content[:100]}...")

                # Second filter: LLM verification
                if self.use_verification and self.verifier:
                    title = f"{app_name} {review.get('score', 0)}-star review"
                    verification = self.verifier.verify(title, content)

                    print(f"   LLM: is_fraud={verification['is_fraud']}, "
                          f"is_upi={verification['is_upi_related']}, "
                          f"type={verification['fraud_type']}")

                    if verification["is_fraud"]:
                        self.stats["llm_verified_fraud"] += 1
                    if verification["is_upi_related"]:
                        self.stats["llm_verified_upi"] += 1

                    # Only save if verified as fraud AND UPI-related
                    if not (verification["is_fraud"] and verification["is_upi_related"]):
                        print(f"   Skipping: Not verified as UPI fraud")
                        continue
                else:
                    verification = None

                # Format and save record
                record = self._format_record(review, app_name, verification)
                self._save_record(record)
                self.scraped_ids.add(review_id)
                fraud_count += 1
                print(f"   SAVED! Total fraud records: {fraud_count}/{target_fraud_count}")

                # Save IDs periodically
                if fraud_count % 10 == 0:
                    self._save_scraped_ids()

        except Exception as e:
            print(f"Error scraping {app_name}: {e}")
            import traceback
            traceback.print_exc()

        self._save_scraped_ids()
        print(f"\n{app_name}: Found {fraud_count} fraud records from {reviews_processed} processed")
        return fraud_count

    def scrape_all_apps(self, target_total: int = 100):
        """
        Scrape reviews from all UPI apps.

        Args:
            target_total: Total target fraud records across all apps
        """
        print(f"\nGoogle Play Store UPI Fraud Scraper")
        print(f"Target: {target_total} verified fraud records")
        print(f"Output: {self.output_file}")
        print(f"Apps: {', '.join(self.UPI_APPS.keys())}")

        # Distribute target evenly across apps
        per_app_target = target_total // len(self.UPI_APPS)
        extra = target_total % len(self.UPI_APPS)

        total_found = 0
        for i, app_name in enumerate(self.UPI_APPS.keys()):
            app_target = per_app_target + (1 if i < extra else 0)

            # Adjust target based on what we've found so far
            remaining = target_total - total_found
            if remaining <= 0:
                print(f"\nReached total target of {target_total}!")
                break

            actual_target = min(app_target, remaining)
            found = self.scrape_app_reviews(app_name,
                                            max_reviews=1000,
                                            target_fraud_count=actual_target)
            total_found += found

        self._print_stats()

    def _print_stats(self):
        """Print scraping statistics."""
        print(f"\n{'='*60}")
        print("SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total reviews fetched:    {self.stats['total_reviews_fetched']}")
        print(f"Fraud keyword matches:    {self.stats['fraud_keyword_matches']}")
        print(f"LLM verified as fraud:    {self.stats['llm_verified_fraud']}")
        print(f"LLM verified as UPI:      {self.stats['llm_verified_upi']}")
        print(f"Records saved:            {self.stats['saved_records']}")
        print(f"Output file:              {self.output_file}")
        print(f"{'='*60}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape UPI app reviews from Google Play Store for fraud detection"
    )
    parser.add_argument(
        "--target", "-t", type=int, default=100,
        help="Target number of fraud records to collect (default: 100)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="data/raw/playstore_upi_fraud.jsonl",
        help="Output JSONL file path"
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip LLM verification (faster but less accurate)"
    )
    parser.add_argument(
        "--app", "-a", type=str, choices=["GPay", "PhonePe", "Paytm", "BHIM"],
        help="Scrape only a specific app"
    )
    parser.add_argument(
        "--lang", "-l", type=str, default="en",
        help="Language code for reviews (en, hi)"
    )
    parser.add_argument(
        "--sort", "-s", type=str, default="newest", choices=["newest", "relevant"],
        help="Sort order for reviews (newest, relevant)"
    )

    args = parser.parse_args()

    scraper = PlayStoreScraper(
        output_file=args.output,
        use_verification=not args.no_verify,
        lang=args.lang,
        sort_order=args.sort
    )

    if args.app:
        scraper.scrape_app_reviews(args.app, max_reviews=1000,
                                   target_fraud_count=args.target)
        scraper._print_stats()
    else:
        scraper.scrape_all_apps(target_total=args.target)


if __name__ == "__main__":
    main()

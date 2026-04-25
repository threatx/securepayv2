# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Reddit Data Converter with LLM Verification

Converts Reddit fraud posts from nilansh_reddit dataset to project JSONL format
with LLM verification for each record.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.scraper.verifier import FraudVerifier


class RedditConverter:
    """Convert Reddit posts to verified JSONL format."""

    def __init__(self, output_file: str = "data/raw/nilansh_reddit_verified.jsonl"):
        """
        Initialize the converter.

        Args:
            output_file: Path to output JSONL file (new file)
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Clear the output file (start fresh)
        if self.output_file.exists():
            self.output_file.unlink()

        # Initialize LLM verifier
        try:
            self.verifier = FraudVerifier()
            print("LLM verification enabled (Groq API)")
        except ValueError as e:
            print(f"Error: {e}")
            raise

        # Stats
        self.stats = {
            "total_posts": 0,
            "llm_verified_fraud": 0,
            "llm_verified_upi": 0,
            "saved_records": 0,
        }

    def _extract_upi_id(self, text: str) -> Optional[str]:
        """Extract UPI ID from text if present."""
        upi_pattern = r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9]+\b'
        matches = re.findall(upi_pattern, text)
        # Filter out email-like patterns
        upi_matches = [m for m in matches if not any(
            domain in m.lower() for domain in ['gmail', 'yahoo', 'hotmail', 'outlook', 'mail', 'reddit']
        )]
        return upi_matches[0] if upi_matches else None

    def _extract_amount(self, text: str) -> Optional[str]:
        """Extract monetary amount from text if present."""
        patterns = [
            r'₹\s*[\d,]+(?:\.\d{2})?',
            r'Rs\.?\s*[\d,]+(?:\.\d{2})?',
            r'INR\s*[\d,]+(?:\.\d{2})?',
            r'(?:rupees?|rs)\s*[\d,]+',
            r'[\d,]+\s*(?:lakh|lac|k)\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None

    def _format_record(self, post: dict, verification: dict) -> dict:
        """Format Reddit post to match project JSONL schema."""
        # Extract post ID from URL
        url = post.get("url", "")
        post_id = url.split("/comments/")[-1].split("/")[0] if "/comments/" in url else ""

        record = {
            "complaint_id": f"reddit_{post.get('subreddit', 'unknown')}_{post_id}",
            "source_url": url,
            "raw_text": post.get("content", ""),
            "title": post.get("title", ""),
            "complainant_name": post.get("author", "Anonymous"),
            "complainant_location": None,
            "company_name": self._detect_company(post.get("content", "") + " " + post.get("title", "")),
            "date_reported": post.get("created", datetime.now().isoformat()),
            "date_scraped": datetime.now().isoformat(),
            "source_query": f"reddit_{post.get('subreddit', 'unknown')}",
            "helpful_yes": post.get("score", 0),
            "helpful_no": 0,
            "status": None,
            "has_images": False,
            "image_urls": [],
            "subreddit": post.get("subreddit", ""),
            "num_comments": post.get("num_comments", 0),
            "extracted_upi_id": self._extract_upi_id(post.get("content", "")),
            "extracted_amount": self._extract_amount(post.get("content", "") + " " + post.get("title", "")),
            "is_fraud_verified": verification.get("is_fraud", False),
            "is_upi_related": verification.get("is_upi_related", False),
            "fraud_type": verification.get("fraud_type"),
            "fraud_confidence": verification.get("confidence", "low"),
            "verification_reason": verification.get("reason", ""),
        }

        return record

    def _detect_company(self, text: str) -> Optional[str]:
        """Detect UPI app/company mentioned in text."""
        text_lower = text.lower()
        if "phonepe" in text_lower or "phone pe" in text_lower:
            return "PhonePe"
        elif "gpay" in text_lower or "google pay" in text_lower:
            return "GPay"
        elif "paytm" in text_lower:
            return "Paytm"
        elif "bhim" in text_lower:
            return "BHIM"
        elif "upi" in text_lower:
            return "UPI"
        return None

    def _save_record(self, record: dict):
        """Append record to JSONL file."""
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self.stats["saved_records"] += 1

    def convert(self, input_file: str, save_all: bool = False):
        """
        Convert Reddit posts to verified JSONL format.

        Args:
            input_file: Path to input JSON file
            save_all: If True, save all records; if False, only save verified fraud+UPI
        """
        print(f"\nReddit Data Converter")
        print(f"Input: {input_file}")
        print(f"Output: {self.output_file}")
        print(f"Mode: {'Save all records' if save_all else 'Only verified fraud+UPI'}")
        print("=" * 60)

        # Load input data
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        posts = data.get("posts", [])
        self.stats["total_posts"] = len(posts)
        print(f"Total posts to process: {len(posts)}")
        print("=" * 60)

        for i, post in enumerate(posts):
            title = post.get("title", "")
            content = post.get("content", "")

            # Skip empty posts
            if not content.strip():
                continue

            # LLM verification
            verification = self.verifier.verify(title, content)

            if verification["is_fraud"]:
                self.stats["llm_verified_fraud"] += 1
            if verification["is_upi_related"]:
                self.stats["llm_verified_upi"] += 1

            # Decide whether to save
            should_save = save_all or (verification["is_fraud"] and verification["is_upi_related"])

            if should_save:
                record = self._format_record(post, verification)
                self._save_record(record)
                print(f"[{i+1}/{len(posts)}] SAVED: {title[:50]}...")
                print(f"         fraud={verification['is_fraud']}, upi={verification['is_upi_related']}, type={verification['fraud_type']}")
            else:
                if (i + 1) % 50 == 0:
                    print(f"[{i+1}/{len(posts)}] Processing... (saved: {self.stats['saved_records']})")

        self._print_stats()

    def _print_stats(self):
        """Print conversion statistics."""
        print(f"\n{'=' * 60}")
        print("CONVERSION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total posts processed:    {self.stats['total_posts']}")
        print(f"LLM verified as fraud:    {self.stats['llm_verified_fraud']}")
        print(f"LLM verified as UPI:      {self.stats['llm_verified_upi']}")
        print(f"Records saved:            {self.stats['saved_records']}")
        print(f"Output file:              {self.output_file}")
        print(f"{'=' * 60}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Reddit fraud posts to verified JSONL format"
    )
    parser.add_argument(
        "--input", "-i", type=str, required=True,
        help="Input JSON file (e.g., india-upi-fraud-FILTERED.json)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="data/raw/nilansh_reddit_verified.jsonl",
        help="Output JSONL file path"
    )
    parser.add_argument(
        "--save-all", action="store_true",
        help="Save all records (not just verified fraud+UPI)"
    )

    args = parser.parse_args()

    converter = RedditConverter(output_file=args.output)
    converter.convert(args.input, save_all=args.save_all)


if __name__ == "__main__":
    main()

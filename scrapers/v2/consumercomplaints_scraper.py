# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
V2 ConsumerComplaints.in Scraper for UPI Fraud
==============================================
Deep scrape of company pages and search queries.
Outputs to v2_upi_fraud.jsonl
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import re
import html
from datetime import date, datetime
from pathlib import Path

from ..verifier import FraudVerifier
from .config import V2_OUTPUT_FILE, V2_SCRAPED_IDS_FILE, load_existing_urls_from_db


class ConsumerComplaintsScraperV2:
    """V2 ConsumerComplaints scraper with deep company page coverage."""

    BASE_URL = "https://www.consumercomplaints.in"
    DELAY = 1.5

    # Company pages to scrape (high UPI fraud content)
    COMPANY_PAGES = [
        ("phonepe-b115681", "PhonePe", 200),           # ~175 pages
        ("google-india-tez-b115703", "Google Pay", 150),  # ~100 pages
        ("paytm-mobile-solutions-b100340", "Paytm", 200),  # ~200 pages
        ("national-payments-corporation-of-india-b100299", "NPCI", 220),  # ~212 pages
        ("mobikwik-b100174", "Mobikwik", 50),
        ("cred-b117831", "CRED", 30),
        ("amazon-india-b106509", "Amazon", 50),        # Lower yield but some UPI fraud
        ("flipkart-b104905", "Flipkart", 30),
    ]

    # Search queries for additional coverage
    SEARCH_QUERIES = [
        # Core UPI fraud
        "upi fraud",
        "upi scam",
        "upi hacked",

        # App-specific
        "phonepe fraud",
        "gpay fraud",
        "paytm upi fraud",
        "bhim fraud",

        # Scam patterns
        "qr code scam",
        "collect request fraud",
        "fake customer care",
        "otp fraud",

        # Platform scams
        "olx upi scam",
        "olx fraud gpay",

        # Task/job scams
        "task fraud upi",
        "job scam gpay",
        "part time fraud phonepe",

        # Bank-specific
        "sbi upi fraud",
        "hdfc upi fraud",
        "icici upi fraud",
        "axis upi fraud",
        "kotak upi fraud",
    ]

    def __init__(self, verify_with_llm: bool = True):
        self.verify_with_llm = verify_with_llm
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        self.scraped_ids = self._load_scraped_ids()
        self.verifier = FraudVerifier() if verify_with_llm else None

        # Load existing URLs from database to avoid duplicates
        self.existing_db_urls = load_existing_urls_from_db()

        V2_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        print(f"LLM verification: {'ENABLED' if self.verify_with_llm else 'DISABLED'}")
        print(f"Loaded {len(self.scraped_ids)} existing complaint IDs")
        print(f"Loaded {len(self.existing_db_urls)} URLs from database")

    def _load_scraped_ids(self) -> set:
        """Load previously scraped complaint IDs."""
        ids = set()

        # Load from tracking file
        if V2_SCRAPED_IDS_FILE.exists():
            with open(V2_SCRAPED_IDS_FILE, 'r') as f:
                data = json.load(f)
                ids.update(data.get('consumercomplaints', []))

        # Load from output file
        if V2_OUTPUT_FILE.exists():
            with open(V2_OUTPUT_FILE, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if record.get('source_platform') == 'consumercomplaints':
                            cid = record.get('complaint_id', '')
                            if cid.startswith('cc_'):
                                ids.add(cid.replace('cc_', ''))

        return ids

    def _save_scraped_ids(self):
        """Save scraped IDs to tracking file."""
        existing = {}
        if V2_SCRAPED_IDS_FILE.exists():
            with open(V2_SCRAPED_IDS_FILE, 'r') as f:
                existing = json.load(f)

        existing['consumercomplaints'] = list(self.scraped_ids)

        with open(V2_SCRAPED_IDS_FILE, 'w') as f:
            json.dump(existing, f)

    def scrape_all(self, target_count: int = 400):
        """
        Scrape all company pages and search queries.

        Args:
            target_count: Stop after this many new verified records
        """
        existing_count = self._count_existing_records()

        print("\n" + "=" * 70)
        print("V2 CONSUMERCOMPLAINTS.IN SCRAPER")
        print("=" * 70)
        print(f"Company pages: {len(self.COMPANY_PAGES)}")
        print(f"Search queries: {len(self.SEARCH_QUERIES)}")
        print(f"Existing records in v2: {existing_count}")
        print(f"Target new records: {target_count}")
        print(f"Output: {V2_OUTPUT_FILE}")
        print("=" * 70)

        total_verified = 0

        try:
            # Phase 1: Scrape company pages (higher yield)
            print("\n" + "=" * 50)
            print("PHASE 1: COMPANY PAGES")
            print("=" * 50)

            for page_slug, company_name, max_pages in self.COMPANY_PAGES:
                if total_verified >= target_count:
                    break

                count = self._scrape_company_page(page_slug, company_name, max_pages, target_count - total_verified)
                total_verified += count
                self._save_scraped_ids()

            # Phase 2: Search queries (for additional coverage)
            if total_verified < target_count:
                print("\n" + "=" * 50)
                print("PHASE 2: SEARCH QUERIES")
                print("=" * 50)

                for query in self.SEARCH_QUERIES:
                    if total_verified >= target_count:
                        break

                    count = self._scrape_search(query, max_pages=20, target_remaining=target_count - total_verified)
                    total_verified += count
                    self._save_scraped_ids()

        finally:
            self._save_scraped_ids()
            self._print_summary(total_verified)

    def _count_existing_records(self) -> int:
        """Count existing ConsumerComplaints records in v2 file."""
        count = 0
        if V2_OUTPUT_FILE.exists():
            with open(V2_OUTPUT_FILE, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if record.get('source_platform') == 'consumercomplaints':
                            count += 1
        return count

    def _scrape_company_page(self, page_slug: str, company_name: str, max_pages: int, target_remaining: int) -> int:
        """Scrape a company page for UPI fraud complaints."""
        print(f"\n[{company_name}] Scraping {page_slug}...")

        total_new = 0
        page = 1
        consecutive_empty = 0

        while page <= max_pages and total_new < target_remaining:
            if page == 1:
                url = f"{self.BASE_URL}/{page_slug}"
            else:
                url = f"{self.BASE_URL}/{page_slug}/page/{page}"

            print(f"  Page {page}...", end=" ")
            page_html = self._fetch(url)

            if not page_html:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print("Too many errors, stopping")
                    break
                page += 1
                continue

            consecutive_empty = 0
            complaint_urls = self._parse_company_page(page_html, page_slug)

            if not complaint_urls:
                print("No complaints found")
                page += 1
                continue

            page_new = 0
            page_rejected = 0
            page_dups = 0

            for complaint_url in complaint_urls:
                match = re.search(r'-c(\d+)$', complaint_url)
                if not match:
                    continue

                complaint_id = match.group(1)

                if complaint_id in self.scraped_ids:
                    page_dups += 1
                    continue

                # Check if URL already exists in database
                if complaint_url.lower() in self.existing_db_urls:
                    page_dups += 1
                    self.scraped_ids.add(complaint_id)  # Mark as scraped
                    continue

                complaint = self._fetch_complaint(complaint_url, complaint_id, company_name)

                if complaint:
                    self._save(complaint)
                    self.scraped_ids.add(complaint_id)
                    page_new += 1
                    total_new += 1

                    if total_new >= target_remaining:
                        break
                else:
                    page_rejected += 1

                time.sleep(self.DELAY)

            print(f"Found {len(complaint_urls)}, New: {page_new}, Rejected: {page_rejected}, Dups: {page_dups}")
            page += 1
            time.sleep(self.DELAY)

        print(f"[{company_name}] Total new: {total_new}")
        return total_new

    def _parse_company_page(self, page_html: str, page_slug: str) -> list:
        """Parse company page for complaint URLs."""
        soup = BeautifulSoup(page_html, 'lxml')
        urls = []

        for link in soup.find_all('a', href=re.compile(r'-c\d+$')):
            href = link.get('href', '')
            if href.startswith('/'):
                href = self.BASE_URL + href
            # Only include complaints from this company
            if page_slug.split('-')[0].lower() in href.lower():
                urls.append(href)

        return list(dict.fromkeys(urls))

    def _scrape_search(self, query: str, max_pages: int, target_remaining: int) -> int:
        """Scrape search results for a query."""
        print(f"\nSearching: '{query}'")

        total_new = 0
        page = 1
        consecutive_empty = 0

        while page <= max_pages and total_new < target_remaining:
            encoded_query = query.replace(' ', '+')
            if page == 1:
                url = f"{self.BASE_URL}/?search={encoded_query}"
            else:
                url = f"{self.BASE_URL}/?search={encoded_query}&page={page}"

            print(f"  Page {page}...", end=" ")
            page_html = self._fetch(url)

            if not page_html:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue

            consecutive_empty = 0
            complaint_urls = self._parse_search_results(page_html)

            if not complaint_urls:
                print("No results")
                break

            page_new = 0
            for complaint_url in complaint_urls:
                match = re.search(r'-c(\d+)$', complaint_url)
                if not match:
                    continue

                complaint_id = match.group(1)
                if complaint_id in self.scraped_ids:
                    continue

                # Check if URL already exists in database
                if complaint_url.lower() in self.existing_db_urls:
                    self.scraped_ids.add(complaint_id)
                    continue

                complaint = self._fetch_complaint(complaint_url, complaint_id, query)

                if complaint:
                    self._save(complaint)
                    self.scraped_ids.add(complaint_id)
                    page_new += 1
                    total_new += 1

                    if total_new >= target_remaining:
                        break

                time.sleep(self.DELAY)

            print(f"New: {page_new}")
            page += 1
            time.sleep(self.DELAY)

        return total_new

    def _parse_search_results(self, page_html: str) -> list:
        """Parse search results page for complaint URLs."""
        soup = BeautifulSoup(page_html, 'lxml')
        urls = []

        for link in soup.find_all('a', href=re.compile(r'-c\d+$')):
            href = link.get('href', '')
            if href.startswith('/'):
                href = self.BASE_URL + href
            urls.append(href)

        return list(dict.fromkeys(urls))

    def _fetch(self, url: str) -> str | None:
        """Fetch URL content."""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"Error: {e}")
            return None

    def _fetch_complaint(self, url: str, complaint_id: str, source: str) -> dict | None:
        """Fetch and verify a single complaint."""
        page_html = self._fetch(url)
        if not page_html:
            return None

        soup = BeautifulSoup(page_html, 'lxml')

        # Title
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else ""

        # Raw text
        raw_text = ""
        for selector in ['[itemprop="reviewBody"]', '.complaint', 'article']:
            content = soup.select_one(selector)
            if content:
                for tag in content(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                raw_text = content.get_text(separator=' ', strip=True)
                if len(raw_text) > 20:
                    break

        raw_text = re.sub(r'Was this information helpful\?.*?Yes\s*\(\d+\)', '', raw_text, flags=re.IGNORECASE | re.DOTALL)
        raw_text = re.sub(r'\+\s*\d+\s*photos?', '', raw_text, flags=re.IGNORECASE)
        raw_text = raw_text.strip()

        if not raw_text or len(raw_text) < 20:
            return None

        # LLM Verification
        is_fraud_verified = False
        is_upi_related = False
        fraud_type = None
        fraud_confidence = None

        if self.verify_with_llm:
            verification = self.verifier.verify(title, raw_text)
            if not verification['is_fraud']:
                return None
            if not verification.get('is_upi_related', False):
                return None
            is_fraud_verified = True
            is_upi_related = True
            fraud_type = verification['fraud_type']
            fraud_confidence = verification['confidence']

        # Extract metadata
        complainant = ""
        complainant_location = None
        date_reported = None

        author_elem = soup.select_one('[itemprop="author"]')
        if author_elem:
            author_text = author_elem.get_text(strip=True)
            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}', author_text)
            if date_match:
                try:
                    dt = datetime.strptime(date_match.group(), '%b %d, %Y')
                    date_reported = dt.strftime('%Y-%m-%d')
                    before_date = author_text[:date_match.start()].strip()
                except:
                    before_date = author_text
            else:
                before_date = author_text

            location_match = re.search(r'from\s+(.+)$', before_date, re.IGNORECASE)
            if location_match:
                complainant_location = location_match.group(1).strip()
                complainant = before_date[:location_match.start()].strip()
            else:
                complainant = before_date

            if len(complainant) > 1 and complainant[0].upper() == complainant[1].upper():
                complainant = complainant[1:]

        # Company name from URL
        company_name = source if source in ["PhonePe", "Google Pay", "Paytm", "NPCI", "Mobikwik", "CRED", "Amazon", "Flipkart"] else "Unknown"
        url_lower = url.lower()
        if 'phonepe' in url_lower:
            company_name = "PhonePe"
        elif 'google' in url_lower or 'tez' in url_lower:
            company_name = "Google Pay"
        elif 'paytm' in url_lower:
            company_name = "Paytm"
        elif 'npci' in url_lower or 'national-payments' in url_lower:
            company_name = "NPCI"

        # Helpful votes
        helpful_yes = 0
        helpful_no = 0
        page_str = str(soup)
        yes_match = re.search(r'Yes\s*\((\d+)\)', page_str, re.IGNORECASE)
        no_match = re.search(r'No\s*\((\d+)\)', page_str, re.IGNORECASE)
        if yes_match:
            helpful_yes = int(yes_match.group(1))
        if no_match:
            helpful_no = int(no_match.group(1))

        # Status
        status = None
        if '[Resolved]' in title or '[resolved]' in title.lower():
            status = 'resolved'

        # Images
        image_urls = []
        thumb_matches = re.findall(r'/thumb\.php\?[^"\'>\s]+', page_str)
        for thumb in thumb_matches:
            thumb_decoded = html.unescape(thumb)
            full_url = self.BASE_URL + thumb_decoded
            if 'complaints=' in thumb and full_url not in image_urls:
                image_urls.append(full_url)

        return {
            'complaint_id': f"cc_{complaint_id}",
            'source_url': url,
            'source_platform': 'consumercomplaints',
            'raw_text': raw_text,
            'title': title,
            'complainant_name': complainant,
            'complainant_location': complainant_location,
            'company_name': company_name,
            'date_reported': date_reported,
            'date_scraped': date.today().isoformat(),
            'source_query': source,
            'helpful_yes': helpful_yes,
            'helpful_no': helpful_no,
            'status': status,
            'has_images': len(image_urls) > 0,
            'image_urls': image_urls,
            'is_fraud_verified': is_fraud_verified,
            'is_upi_related': is_upi_related,
            'fraud_type': fraud_type,
            'fraud_confidence': fraud_confidence,
        }

    def _save(self, complaint: dict):
        """Save complaint to v2 output file."""
        with open(V2_OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(complaint, ensure_ascii=False) + '\n')

    def _print_summary(self, total_verified: int):
        """Print scraping summary."""
        print("\n" + "=" * 70)
        print("V2 CONSUMERCOMPLAINTS SUMMARY")
        print("=" * 70)
        print(f"Total verified & saved: {total_verified}")
        print(f"Total IDs tracked: {len(self.scraped_ids)}")
        print(f"Output file: {V2_OUTPUT_FILE}")
        print("=" * 70)


if __name__ == "__main__":
    scraper = ConsumerComplaintsScraperV2(verify_with_llm=True)
    scraper.scrape_all(target_count=400)

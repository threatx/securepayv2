# AI-Assisted Development Notice
# This file was developed with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: making code cleaner and well-structured, implementing complex code logic
# Student contribution: high-level pseudocode, coding, requirements definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

#!/usr/bin/env python3
"""
check_dedup.py — Called by dedup_checker agent.
Usage: python3 scripts/check_dedup.py '<source_url>'
Prints: "duplicate" or "unique"
"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")

def main():
    if len(sys.argv) < 2:
        print("ERROR: no source_url provided", file=sys.stderr)
        sys.exit(1)

    source_url = sys.argv[1].strip()
    if not source_url:
        print("unique")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM scenario_sources WHERE source_post_url = %s LIMIT 1",
                (source_url,)
            )
            row = cur.fetchone()
        conn.close()
        print("duplicate" if row else "unique")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

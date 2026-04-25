# AI-Assisted Development Notice
# This file was developed with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: implementing complex code logic
# Student contribution: coding, architecture design, requirements definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

#!/usr/bin/env python3
"""
Generate 4-Level Hierarchical Embeddings for SecurePay

Levels:
1. Canonical Form (Scenario raw_text)
2. Taxonomy (Scenario types)
3. Mechanisms (How scam works)
4. Red Flags (Warning signs)

Uses Cohere embed-english-v3.0 (1024 dimensions)
"""

import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import cohere
from typing import List, Tuple
import time

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/securepay")

# Cohere setup
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    print("ERROR: COHERE_API_KEY not found in environment")
    sys.exit(1)

co = cohere.Client(COHERE_API_KEY)
MODEL = "embed-english-v3.0"
BATCH_SIZE = 96  # Cohere limit


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_embeddings_batch(texts: List[str], input_type: str = "search_document") -> List[List[float]]:
    """
    Generate embeddings for a batch of texts.

    Args:
        texts: List of texts to embed
        input_type: "search_document" for storage, "search_query" for queries

    Returns:
        List of embeddings (1024 dimensions each)
    """
    if not texts:
        return []

    try:
        response = co.embed(
            texts=texts,
            model=MODEL,
            input_type=input_type
        )
        return response.embeddings
    except cohere.TooManyRequestsError as e:
        print(f"Rate limit hit. Waiting 60 seconds...")
        time.sleep(60)
        return get_embeddings_batch(texts, input_type)
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        raise


def process_in_batches(items: List[Tuple], text_formatter, update_func, batch_size: int = BATCH_SIZE):
    """
    Process items in batches and update database.

    Args:
        items: List of (id, text_data) tuples
        text_formatter: Function to format text for embedding
        update_func: Function to update database with embeddings
        batch_size: Number of items per batch
    """
    total = len(items)
    processed = 0

    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        ids = [item[0] for item in batch]
        texts = [text_formatter(item) for item in batch]

        print(f"  Processing batch {i//batch_size + 1} ({len(batch)} items)...")
        embeddings = get_embeddings_batch(texts)

        update_func(ids, embeddings)
        processed += len(batch)
        print(f"  Progress: {processed}/{total}")

        # Small delay to avoid rate limits
        time.sleep(0.5)


def generate_scenario_embeddings(conn):
    """Level 1: Generate embeddings for approved scenarios (raw_text)."""
    print("\n=== Level 1: Scenario Embeddings (raw_text) ===")

    cur = conn.cursor()

    # Get scenarios without embeddings
    cur.execute("""
        SELECT scenario_id, raw_text
        FROM scenarios
        WHERE embedding IS NULL
    """)
    scenarios = cur.fetchall()

    if not scenarios:
        print("  All scenarios already have embeddings.")
        return

    print(f"  Found {len(scenarios)} scenarios to process")

    def text_formatter(item):
        return item[1][:8000]  # Truncate very long texts

    def update_db(ids, embeddings):
        for sid, emb in zip(ids, embeddings):
            cur.execute(
                "UPDATE scenarios SET embedding = %s WHERE scenario_id = %s",
                (emb, sid)
            )
        conn.commit()

    process_in_batches(scenarios, text_formatter, update_db)
    print(f"  ✓ Generated embeddings for {len(scenarios)} scenarios")


def generate_scenario_type_embeddings(conn):
    """Level 2: Generate embeddings for scenario types."""
    print("\n=== Level 2: Scenario Type Embeddings ===")

    cur = conn.cursor()

    # Get types without embeddings
    cur.execute("""
        SELECT type_id, type_name, description
        FROM scenario_types
        WHERE embedding IS NULL
    """)
    types = cur.fetchall()

    if not types:
        print("  All scenario types already have embeddings.")
        return

    print(f"  Found {len(types)} types to process")

    def text_formatter(item):
        type_name = item[1].replace('_', ' ')
        description = item[2] or f"UPI fraud category: {type_name}"
        return f"Scam type: {type_name}. {description}"

    def update_db(ids, embeddings):
        for tid, emb in zip(ids, embeddings):
            cur.execute(
                "UPDATE scenario_types SET embedding = %s WHERE type_id = %s",
                (emb, tid)
            )
        conn.commit()

    process_in_batches(types, text_formatter, update_db)
    print(f"  ✓ Generated embeddings for {len(types)} scenario types")


def generate_mechanism_embeddings(conn):
    """Level 3: Generate embeddings for mechanisms."""
    print("\n=== Level 3: Mechanism Embeddings ===")

    cur = conn.cursor()

    # Get mechanisms without embeddings
    cur.execute("""
        SELECT mechanism_id, mechanism_name, description
        FROM mechanisms
        WHERE embedding IS NULL
    """)
    mechanisms = cur.fetchall()

    if not mechanisms:
        print("  All mechanisms already have embeddings.")
        return

    print(f"  Found {len(mechanisms)} mechanisms to process")

    def text_formatter(item):
        name = item[1].replace('_', ' ')
        description = item[2]
        return f"Scam technique: {name}. {description}"

    def update_db(ids, embeddings):
        for mid, emb in zip(ids, embeddings):
            cur.execute(
                "UPDATE mechanisms SET embedding = %s WHERE mechanism_id = %s",
                (emb, mid)
            )
        conn.commit()

    process_in_batches(mechanisms, text_formatter, update_db)
    print(f"  ✓ Generated embeddings for {len(mechanisms)} mechanisms")


def generate_red_flag_embeddings(conn):
    """Level 4: Generate embeddings for red flags."""
    print("\n=== Level 4: Red Flag Embeddings ===")

    cur = conn.cursor()

    # Get red flags without embeddings
    cur.execute("""
        SELECT red_flag_id, red_flag_name, description
        FROM red_flags
        WHERE embedding IS NULL
    """)
    red_flags = cur.fetchall()

    if not red_flags:
        print("  All red flags already have embeddings.")
        return

    print(f"  Found {len(red_flags)} red flags to process")

    def text_formatter(item):
        name = item[1].replace('_', ' ')
        description = item[2]
        return f"Warning sign: {name}. {description}"

    def update_db(ids, embeddings):
        for rfid, emb in zip(ids, embeddings):
            cur.execute(
                "UPDATE red_flags SET embedding = %s WHERE red_flag_id = %s",
                (emb, rfid)
            )
        conn.commit()

    process_in_batches(red_flags, text_formatter, update_db)
    print(f"  ✓ Generated embeddings for {len(red_flags)} red flags")


def print_summary(conn):
    """Print summary of embeddings."""
    cur = conn.cursor()

    print("\n" + "="*50)
    print("EMBEDDING SUMMARY")
    print("="*50)

    # Scenarios
    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM scenarios")
    total, with_emb = cur.fetchone()
    print(f"Level 1 - Scenarios:     {with_emb}/{total} have embeddings")

    # Scenario types
    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM scenario_types")
    total, with_emb = cur.fetchone()
    print(f"Level 2 - Types:         {with_emb}/{total} have embeddings")

    # Mechanisms
    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM mechanisms")
    total, with_emb = cur.fetchone()
    print(f"Level 3 - Mechanisms:    {with_emb}/{total} have embeddings")

    # Red flags
    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM red_flags")
    total, with_emb = cur.fetchone()
    print(f"Level 4 - Red Flags:     {with_emb}/{total} have embeddings")

    print("="*50)


def main():
    """Main entry point."""
    print("="*50)
    print("4-Level Hierarchical Embedding Generator")
    print("="*50)

    conn = get_db_connection()

    try:
        # Generate embeddings for all 4 levels
        generate_scenario_embeddings(conn)
        generate_scenario_type_embeddings(conn)
        generate_mechanism_embeddings(conn)
        generate_red_flag_embeddings(conn)

        # Print summary
        print_summary(conn)

        print("\n✓ All embeddings generated successfully!")

    except Exception as e:
        print(f"\nERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

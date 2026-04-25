# AI-Assisted Development Notice
# This file was developed by the student with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: writing test statements
# Student contribution: core implementation, architecture, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Semantic Search Module
======================
Uses Cohere embed-v3 for pattern-aware similarity search.
"""

import numpy as np
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.backend.db import get_connection
from app.backend.embeddings import get_query_embedding
from pgvector.psycopg2 import register_vector


def search_scenarios(query: str, top_k: int = 5):
    """
    Search scenarios by semantic similarity.

    Uses Cohere's search_query embedding type for optimal retrieval.
    """
    query_embedding = np.array(get_query_embedding(query))

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    cur.execute("""
        SELECT scenario_id, raw_text, scenario_type, is_scam,
               1 - (embedding <=> %s::vector) AS similarity
        FROM scenarios
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, top_k))

    results = cur.fetchall()
    conn.close()

    return results


def search_iocs(query: str, top_k: int = 5):
    """
    Search IOCs by semantic similarity.

    Uses Cohere's search_query embedding type for optimal retrieval.
    """
    query_embedding = np.array(get_query_embedding(query))

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    cur.execute("""
        SELECT ioc_id, ioc_type, ioc_value, is_scam,
               1 - (embedding <=> %s::vector) AS similarity
        FROM iocs
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, top_k))

    results = cur.fetchall()
    conn.close()

    return results


# Test
if __name__ == "__main__":
    print("=" * 70)
    print("TESTING COHERE EMBED-V3 RETRIEVAL")
    print("=" * 70)

    # Test 1: KYC scam query
    print("\n--- TEST 1: KYC Scam Query ---")
    query = "Someone called from bank saying KYC expired, asked to pay money via UPI"
    print(f"Query: {query}\n")

    results = search_scenarios(query)
    for i, r in enumerate(results, 1):
        print(f"#{i} Similarity: {r[4]:.1%} | Type: {r[2]}")
        print(f"   Text: {r[1][:150]}...")
        print()

    # Test 2: QR code scam query
    print("\n--- TEST 2: QR Code Scam Query ---")
    query = "Seller sent QR code to receive payment but money got deducted instead"
    print(f"Query: {query}\n")

    results = search_scenarios(query)
    for i, r in enumerate(results, 1):
        print(f"#{i} Similarity: {r[4]:.1%} | Type: {r[2]}")
        print(f"   Text: {r[1][:150]}...")
        print()

    # Test 3: Job scam query
    print("\n--- TEST 3: Job Scam Query ---")
    query = "Got job offer on Telegram, asked to complete tasks and deposit money"
    print(f"Query: {query}\n")

    results = search_scenarios(query)
    for i, r in enumerate(results, 1):
        print(f"#{i} Similarity: {r[4]:.1%} | Type: {r[2]}")
        print(f"   Text: {r[1][:150]}...")
        print()

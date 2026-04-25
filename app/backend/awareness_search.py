"""
Awareness Content Search
========================
Semantic similarity search over awareness_content table using Cohere embeddings.
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.backend.db import get_connection
from app.backend.embeddings import get_query_embedding
from pgvector.psycopg2 import register_vector


def search_awareness(query: str, top_k: int = 5, content_type: str = None):
    """
    Search awareness content by semantic similarity.

    Args:
        query: User's search query
        top_k: Number of results to return
        content_type: Optional filter (news_update, prevention_tip, scam_explainer)

    Returns:
        List of tuples: (content_id, title, content_text, content_type, related_scam_types, source_url, similarity)
    """
    query_embedding = np.array(get_query_embedding(query))

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    if content_type:
        cur.execute("""
            SELECT content_id, title, content_text, content_type, related_scam_types, source_url,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM awareness_content
            WHERE embedding IS NOT NULL AND content_type = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, content_type, query_embedding, top_k))
    else:
        cur.execute("""
            SELECT content_id, title, content_text, content_type, related_scam_types, source_url,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM awareness_content
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, top_k))

    results = cur.fetchall()
    conn.close()

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("TESTING AWARENESS CONTENT SEARCH")
    print("=" * 60)

    queries = [
        "How do QR code scams work?",
        "What should I do if I was scammed via UPI?",
        "How to stay safe while using UPI payments?",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        results = search_awareness(query, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  #{i} [{r[3]}] Sim: {r[6]:.1%} | {r[1][:60]}...")
        print()

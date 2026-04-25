# AI-Assisted Development Notice
# This file was developed by the student with AI used for code review (Anthropic, 2026).
# AI was used for: code review, syntax corrections, formatting, sentence construction, and prompt construction for LLM calls
# Student contribution: entire code written by student — architecture, implementation, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
4-Level Hierarchical Search for SecurePay

Performs semantic search across:
1. Scenarios (raw_text embeddings)
2. Scenario Types (taxonomy categories)
3. Mechanisms (how scams work)
4. Red Flags (warning signs)

Returns results from all levels with relevance scores.
"""

import os
import json
import psycopg2
import numpy as np
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
import cohere

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/securepay")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

co = cohere.Client(COHERE_API_KEY)


@dataclass
class SearchResult:
    """Single search result with metadata."""
    level: str
    id: str
    name: str
    description: str
    similarity: float
    metadata: Dict[str, Any]


def get_query_embedding(query: str) -> List[float]:
    """Generate embedding for a search query."""
    response = co.embed(
        texts=[query],
        model="embed-english-v3.0",
        input_type="search_query"
    )
    return response.embeddings[0]


def search_scenarios(
    conn,
    query_embedding: List[float],
    limit: int = 5
) -> List[Dict]:
    """Search Level 1: Scenarios."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            scenario_id,
            summary,
            LEFT(raw_text, 200) as preview,
            scenario_type,
            loss_amount,
            1 - (embedding <=> %s::vector) as similarity
        FROM scenarios
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))

    results = []
    for row in cur.fetchall():
        results.append({
            "level": "scenario",
            "id": str(row["scenario_id"]),
            "name": row["summary"] or "Untitled scenario",
            "description": row["preview"] + "...",
            "similarity": round(row["similarity"], 4),
            "metadata": {
                "scenario_type": row["scenario_type"],
                "loss_amount": float(row["loss_amount"]) if row["loss_amount"] else None
            }
        })

    return results


def search_scenario_types(
    conn,
    query_embedding: List[float],
    limit: int = 3
) -> List[Dict]:
    """Search Level 2: Scenario Types (taxonomy)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            type_id,
            type_name,
            description,
            scenario_count,
            1 - (embedding <=> %s::vector) as similarity
        FROM scenario_types
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))

    results = []
    for row in cur.fetchall():
        results.append({
            "level": "type",
            "id": row["type_id"],
            "name": row["type_name"].replace("_", " ").title(),
            "description": row["description"],
            "similarity": round(row["similarity"], 4),
            "metadata": {
                "scenario_count": row["scenario_count"]
            }
        })

    return results


def search_mechanisms(
    conn,
    query_embedding: List[float],
    limit: int = 5
) -> List[Dict]:
    """Search Level 3: Mechanisms (how scams work)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            mechanism_id,
            mechanism_name,
            description,
            scenario_count,
            1 - (embedding <=> %s::vector) as similarity
        FROM mechanisms
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))

    results = []
    for row in cur.fetchall():
        results.append({
            "level": "mechanism",
            "id": row["mechanism_id"],
            "name": row["mechanism_name"].replace("_", " ").title(),
            "description": row["description"],
            "similarity": round(row["similarity"], 4),
            "metadata": {
                "scenario_count": row["scenario_count"]
            }
        })

    return results


def search_red_flags(
    conn,
    query_embedding: List[float],
    limit: int = 5
) -> List[Dict]:
    """Search Level 4: Red Flags (warning signs)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            red_flag_id,
            red_flag_name,
            description,
            scenario_count,
            1 - (embedding <=> %s::vector) as similarity
        FROM red_flags
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))

    results = []
    for row in cur.fetchall():
        results.append({
            "level": "red_flag",
            "id": row["red_flag_id"],
            "name": row["red_flag_name"].replace("_", " ").title(),
            "description": row["description"],
            "similarity": round(row["similarity"], 4),
            "metadata": {
                "scenario_count": row["scenario_count"]
            }
        })

    return results


def hierarchical_search(
    query: str,
    limits: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Perform hierarchical search across all 4 levels.

    Args:
        query: Search query text
        limits: Optional dict with limits per level
            {
                "scenarios": 5,
                "types": 3,
                "mechanisms": 5,
                "red_flags": 5
            }

    Returns:
        Dict with results from all levels and metadata
    """
    if limits is None:
        limits = {
            "scenarios": 5,
            "types": 3,
            "mechanisms": 5,
            "red_flags": 5
        }

    # Generate query embedding
    query_embedding = get_query_embedding(query)

    conn = psycopg2.connect(DATABASE_URL)

    try:
        results = {
            "query": query,
            "levels": {
                "scenarios": search_scenarios(conn, query_embedding, limits.get("scenarios", 5)),
                "types": search_scenario_types(conn, query_embedding, limits.get("types", 3)),
                "mechanisms": search_mechanisms(conn, query_embedding, limits.get("mechanisms", 5)),
                "red_flags": search_red_flags(conn, query_embedding, limits.get("red_flags", 5))
            },
            "totals": {}
        }

        # Add totals
        for level, items in results["levels"].items():
            results["totals"][level] = len(items)

    finally:
        conn.close()

    return results


def get_related_scenarios(
    mechanism_id: Optional[str] = None,
    red_flag_id: Optional[str] = None,
    type_name: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Get scenarios related to a specific mechanism, red flag, or type.

    Use this for drill-down from search results.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        if mechanism_id:
            cur.execute("""
                SELECT
                    s.scenario_id,
                    s.summary,
                    LEFT(s.raw_text, 200) as preview,
                    s.scenario_type,
                    s.loss_amount
                FROM scenarios s
                JOIN scenario_mechanisms sm ON s.scenario_id = sm.scenario_id
                WHERE sm.mechanism_id = %s                 LIMIT %s
            """, (mechanism_id, limit))

        elif red_flag_id:
            cur.execute("""
                SELECT
                    s.scenario_id,
                    s.summary,
                    LEFT(s.raw_text, 200) as preview,
                    s.scenario_type,
                    s.loss_amount
                FROM scenarios s
                JOIN scenario_red_flags srf ON s.scenario_id = srf.scenario_id
                WHERE srf.red_flag_id = %s                 LIMIT %s
            """, (red_flag_id, limit))

        elif type_name:
            cur.execute("""
                SELECT
                    scenario_id,
                    summary,
                    LEFT(raw_text, 200) as preview,
                    scenario_type,
                    loss_amount
                FROM scenarios
                WHERE %s = ANY(scenario_type)
                LIMIT %s
            """, (type_name, limit))

        else:
            return []

        results = []
        for row in cur.fetchall():
            results.append({
                "scenario_id": str(row["scenario_id"]),
                "summary": row["summary"] or "Untitled scenario",
                "preview": row["preview"] + "...",
                "scenario_type": row["scenario_type"],
                "loss_amount": float(row["loss_amount"]) if row["loss_amount"] else None
            })

        return results

    finally:
        conn.close()


# ============================================================================
# MULTI-SIGNAL SEARCH (Late Fusion with Weighted Scoring)
# ============================================================================

def search_by_canonical(
    conn,
    query_embedding: List[float],
    limit: int = 50
) -> Dict[str, float]:
    """Search scenarios by raw_text embedding similarity."""
    cur = conn.cursor()
    cur.execute("""
        SELECT scenario_id, 1 - (embedding <=> %s::vector) as similarity
        FROM scenarios
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit))

    return {str(row[0]): row[1] for row in cur.fetchall()}


def search_by_type(
    conn,
    type_id: str
) -> Dict[str, float]:
    """Find scenarios with matching type (exact match = 1.0)."""
    if not type_id:
        return {}

    cur = conn.cursor()
    cur.execute("""
        SELECT scenario_id
        FROM scenarios
        WHERE %s = ANY(scenario_type)
    """, (type_id,))

    return {str(row[0]): 1.0 for row in cur.fetchall()}


def search_by_mechanism_embeddings(
    conn,
    query_mech_embeddings: List[List[float]],
    candidate_ids: Optional[List[str]] = None,
    limit: int = 50
) -> Dict[str, float]:
    """
    Find scenarios by embedding similarity between query mechanism descriptions
    and scenario mechanism embeddings.

    Score = avg(max(cosine_sim)) across query mechanisms.
    For each query mechanism, find the best-matching mechanism in the scenario,
    then average those best-match scores.

    Args:
        conn: Database connection
        query_mech_embeddings: List of embedding vectors for query mechanisms
        candidate_ids: Optional list of scenario IDs to restrict search to
        limit: Max results to return

    Returns:
        Dict of scenario_id -> mechanism similarity score
    """
    if not query_mech_embeddings:
        return {}

    cur = conn.cursor()

    # Get all scenarios that have mechanisms linked
    if candidate_ids:
        cur.execute("""
            SELECT DISTINCT sm.scenario_id, sm.mechanism_id, m.embedding
            FROM scenario_mechanisms sm
            JOIN mechanisms m ON sm.mechanism_id = m.mechanism_id
            JOIN scenarios s ON sm.scenario_id = s.scenario_id
            WHERE m.embedding IS NOT NULL
              AND sm.scenario_id = ANY(%s::uuid[])
        """, (candidate_ids,))
    else:
        cur.execute("""
            SELECT DISTINCT sm.scenario_id, sm.mechanism_id, m.embedding
            FROM scenario_mechanisms sm
            JOIN mechanisms m ON sm.mechanism_id = m.mechanism_id
            JOIN scenarios s ON sm.scenario_id = s.scenario_id
            WHERE m.embedding IS NOT NULL
        """)

    rows = cur.fetchall()
    if not rows:
        return {}

    # Group mechanism embeddings by scenario
    scenario_mechs = {}  # {scenario_id: [embedding_vector, ...]}
    for row in rows:
        sid = str(row[0])
        emb = row[2]
        if isinstance(emb, str):
            emb = json.loads(emb)
        if sid not in scenario_mechs:
            scenario_mechs[sid] = []
        scenario_mechs[sid].append(np.array(emb, dtype=np.float32))

    query_embs = [np.array(e) for e in query_mech_embeddings]

    # Compute avg-max similarity for each scenario
    scores = {}
    for sid, s_embs in scenario_mechs.items():
        max_sims = []
        for q_emb in query_embs:
            # For this query mechanism, find best match among scenario's mechanisms
            best_sim = max(
                float(np.dot(q_emb, s_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(s_emb) + 1e-10))
                for s_emb in s_embs
            )
            max_sims.append(best_sim)
        scores[sid] = sum(max_sims) / len(max_sims)

    # Sort and limit
    sorted_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit])
    return sorted_scores


def search_by_red_flag_embeddings(
    conn,
    query_rf_embeddings: List[List[float]],
    candidate_ids: Optional[List[str]] = None,
    limit: int = 50
) -> Dict[str, float]:
    """
    Find scenarios by embedding similarity between query red flag descriptions
    and scenario red flag embeddings.

    Score = avg(max(cosine_sim)) across query red flags.

    Args:
        conn: Database connection
        query_rf_embeddings: List of embedding vectors for query red flags
        candidate_ids: Optional list of scenario IDs to restrict search to
        limit: Max results to return

    Returns:
        Dict of scenario_id -> red flag similarity score
    """
    if not query_rf_embeddings:
        return {}

    cur = conn.cursor()

    if candidate_ids:
        cur.execute("""
            SELECT DISTINCT srf.scenario_id, srf.red_flag_id, rf.embedding
            FROM scenario_red_flags srf
            JOIN red_flags rf ON srf.red_flag_id = rf.red_flag_id
            JOIN scenarios s ON srf.scenario_id = s.scenario_id
            WHERE rf.embedding IS NOT NULL
              AND srf.scenario_id = ANY(%s::uuid[])
        """, (candidate_ids,))
    else:
        cur.execute("""
            SELECT DISTINCT srf.scenario_id, srf.red_flag_id, rf.embedding
            FROM scenario_red_flags srf
            JOIN red_flags rf ON srf.red_flag_id = rf.red_flag_id
            JOIN scenarios s ON srf.scenario_id = s.scenario_id
            WHERE rf.embedding IS NOT NULL
        """)

    rows = cur.fetchall()
    if not rows:
        return {}

    scenario_rfs = {}
    for row in rows:
        sid = str(row[0])
        emb = row[2]
        if isinstance(emb, str):
            emb = json.loads(emb)
        if sid not in scenario_rfs:
            scenario_rfs[sid] = []
        scenario_rfs[sid].append(np.array(emb, dtype=np.float32))

    query_embs = [np.array(e) for e in query_rf_embeddings]

    scores = {}
    for sid, s_embs in scenario_rfs.items():
        max_sims = []
        for q_emb in query_embs:
            best_sim = max(
                float(np.dot(q_emb, s_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(s_emb) + 1e-10))
                for s_emb in s_embs
            )
            max_sims.append(best_sim)
        scores[sid] = sum(max_sims) / len(max_sims)

    sorted_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit])
    return sorted_scores


def multi_signal_search(
    query: str,
    patterns: dict,
    weights: dict = None,
    top_k: int = 10
) -> List[dict]:
    """
    Search using 4 signals with weighted late fusion.

    Signals:
    1. canonical: raw_text embedding similarity
    2. type: exact type match (1.0 if match)
    3. mechanism: avg-max embedding similarity between query mechanism descriptions
       and scenario mechanism embeddings
    4. red_flag: avg-max embedding similarity between query red flag descriptions
       and scenario red flag embeddings

    Args:
        query: User's search query
        patterns: Enriched extracted patterns:
            {
                "type": str or None,
                "mechanisms": [{"id", "name", "description", "embedding": [...]}],
                "red_flags": [{"id", "name", "description", "embedding": [...]}]
            }
        weights: Signal weights
        top_k: Number of results to return

    Returns:
        List of scenarios with fused scores and breakdown
    """
    if weights is None:
        weights = {
            "canonical": 0.10,
            "type": 0.15,
            "mechanism": 0.40,
            "red_flag": 0.35
        }

    # Generate query embedding
    query_embedding = get_query_embedding(query)

    conn = psycopg2.connect(DATABASE_URL)

    try:
        # Signal 1 & 2: Text similarity and type match
        canonical_scores = search_by_canonical(conn, query_embedding)
        type_scores = search_by_type(conn, patterns.get("type"))

        # Signal 3: Mechanism embedding similarity (avg-max) — all reviewed scenarios
        query_mech_embeddings = [
            m["embedding"] for m in patterns.get("mechanisms", [])
            if m.get("embedding")
        ]
        mechanism_scores = search_by_mechanism_embeddings(
            conn, query_mech_embeddings
        )

        # Signal 4: Red flag embedding similarity (avg-max) — all reviewed scenarios
        query_rf_embeddings = [
            r["embedding"] for r in patterns.get("red_flags", [])
            if r.get("embedding")
        ]
        red_flag_scores = search_by_red_flag_embeddings(
            conn, query_rf_embeddings
        )

        # Collect all scenario IDs
        all_ids = set(canonical_scores.keys()) | set(type_scores.keys()) | \
                  set(mechanism_scores.keys()) | set(red_flag_scores.keys())

        # Fuse scores
        results = []
        for sid in all_ids:
            breakdown = {
                "canonical": canonical_scores.get(sid, 0),
                "type": type_scores.get(sid, 0),
                "mechanism": mechanism_scores.get(sid, 0),
                "red_flag": red_flag_scores.get(sid, 0)
            }

            final_score = sum(
                breakdown[signal] * weights[signal]
                for signal in weights
            )

            results.append({
                "scenario_id": sid,
                "score": round(final_score, 4),
                "breakdown": {k: round(v, 4) for k, v in breakdown.items()}
            })

        # Sort by final score
        results.sort(key=lambda x: x["score"], reverse=True)

        # Enrich top results with scenario details
        top_results = results[:top_k]
        if top_results:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            ids = [r["scenario_id"] for r in top_results]
            cur.execute("""
                SELECT scenario_id, summary, raw_text as preview,
                       scenario_type, loss_amount
                FROM scenarios
                WHERE scenario_id = ANY(%s::uuid[])
            """, (ids,))

            details = {str(row["scenario_id"]): row for row in cur.fetchall()}

            for r in top_results:
                if r["scenario_id"] in details:
                    d = details[r["scenario_id"]]
                    r["summary"] = d["summary"]
                    r["preview"] = d["preview"]
                    r["scenario_type"] = d["scenario_type"]
                    r["loss_amount"] = float(d["loss_amount"]) if d["loss_amount"] else None

        return top_results

    finally:
        conn.close()


# Example usage
if __name__ == "__main__":
    # Test search
    query = "someone asking for OTP on phone pretending to be bank"
    print(f"Query: {query}\n")

    results = hierarchical_search(query)

    print("=== SCENARIO TYPES ===")
    for r in results["levels"]["types"]:
        print(f"  [{r['similarity']:.3f}] {r['name']}")

    print("\n=== MECHANISMS ===")
    for r in results["levels"]["mechanisms"]:
        print(f"  [{r['similarity']:.3f}] {r['name']}")

    print("\n=== RED FLAGS ===")
    for r in results["levels"]["red_flags"]:
        print(f"  [{r['similarity']:.3f}] {r['name']}")

    print("\n=== SCENARIOS ===")
    for r in results["levels"]["scenarios"]:
        print(f"  [{r['similarity']:.3f}] {r['name'][:60]}...")

# AI-Assisted Development Notice
# This file was developed by the student with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: formatting and syntax
# Student contribution: core implementation, architecture, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Community Scam Submissions Module
==================================
Handles submission, listing, filtering, and semantic search
for community-reported scam stories.
"""

import json
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.backend.db import get_connection
from app.backend.embeddings import get_document_embedding, get_query_embedding
from pgvector.psycopg2 import register_vector

TABLE = "community_reports"


def ensure_table():
    """Create community_reports table if it doesn't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            incident_description TEXT NOT NULL,
            scam_type VARCHAR,
            loss_amount NUMERIC,
            iocs JSONB DEFAULT '[]'::jsonb,
            submitter_alias VARCHAR(100),
            status VARCHAR DEFAULT 'pending',
            importance_score FLOAT DEFAULT 0.5,
            embedding VECTOR(1024),
            submitted_at TIMESTAMP DEFAULT NOW(),
            reviewed_at TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


# Create table on module load
try:
    ensure_table()
except Exception:
    pass  # Will fail at runtime with a clear error if table missing


def submit_scam_story(incident_description, scam_type=None, loss_amount=None,
                      iocs=None, submitter_alias=None):
    """
    Insert a community scam submission with embedding.

    Returns:
        submission_id (UUID string)
    """
    embedding = get_document_embedding(incident_description)

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    cur.execute(f"""
        INSERT INTO {TABLE}
            (incident_description, scam_type, loss_amount, iocs,
             submitter_alias, embedding, status)
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, 'pending')
        RETURNING submission_id
    """, (
        incident_description,
        scam_type,
        loss_amount,
        json.dumps(iocs or []),
        submitter_alias,
        embedding
    ))

    submission_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    conn.close()

    return submission_id


def list_submissions(status=None, scam_type=None, limit=50, offset=0):
    """List submissions with optional filters."""
    conn = get_connection()
    cur = conn.cursor()

    query = f"""
        SELECT submission_id, incident_description, scam_type,
               loss_amount, iocs, submitter_alias, status,
               importance_score, submitted_at
        FROM {TABLE}
        WHERE incident_description IS NOT NULL
    """
    params = []

    if status:
        query += " AND status = %s"
        params.append(status)
    if scam_type:
        query += " AND scam_type = %s"
        params.append(scam_type)

    query += " ORDER BY submitted_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cur.execute(query, params)
    rows = cur.fetchall()

    submissions = []
    for r in rows:
        submissions.append({
            "submission_id": str(r[0]),
            "incident_description": r[1],
            "scam_type": r[2],
            "loss_amount": float(r[3]) if r[3] else None,
            "iocs": r[4] if r[4] else [],
            "submitter_alias": r[5],
            "status": r[6],
            "importance_score": r[7],
            "submitted_at": r[8].isoformat() if r[8] else None
        })

    cur.close()
    conn.close()
    return submissions


def search_submissions(query_text, top_k=5):
    """Semantic search over community submissions using pgvector."""
    query_embedding = np.array(get_query_embedding(query_text))

    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    cur.execute(f"""
        SELECT submission_id, incident_description, scam_type,
               loss_amount, iocs, submitter_alias, status, submitted_at,
               1 - (embedding <=> %s::vector) AS similarity
        FROM {TABLE}
        WHERE embedding IS NOT NULL
          AND incident_description IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, top_k))

    results = []
    for r in cur.fetchall():
        results.append({
            "submission_id": str(r[0]),
            "incident_description": r[1],
            "scam_type": r[2],
            "loss_amount": float(r[3]) if r[3] else None,
            "iocs": r[4] if r[4] else [],
            "submitter_alias": r[5],
            "status": r[6],
            "submitted_at": r[7].isoformat() if r[7] else None,
            "similarity": round(r[8], 4)
        })

    cur.close()
    conn.close()
    return results


def get_submission_stats():
    """Get aggregate stats about community submissions."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE incident_description IS NOT NULL")
    total = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE status = 'pending'")
    pending = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE status = 'verified'")
    verified = cur.fetchone()[0]

    cur.execute(f"""
        SELECT scam_type, COUNT(*)
        FROM {TABLE}
        WHERE scam_type IS NOT NULL AND incident_description IS NOT NULL
        GROUP BY scam_type
        ORDER BY COUNT(*) DESC
    """)
    by_type = [{"scam_type": r[0], "count": r[1]} for r in cur.fetchall()]

    cur.close()
    conn.close()

    return {
        "total": total,
        "pending": pending,
        "verified": verified,
        "by_type": by_type
    }


def review_submission(submission_id: str, status: str):
    """Update status of a community submission. status must be 'verified' or 'rejected'."""
    if status not in ('verified', 'rejected'):
        raise ValueError("status must be 'verified' or 'rejected'")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {TABLE} SET status = %s, reviewed_at = NOW() WHERE submission_id = %s RETURNING submission_id",
        (status, submission_id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not row:
        raise ValueError("Submission not found")
    return str(row[0])

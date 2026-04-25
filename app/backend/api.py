# AI-Assisted Development Notice
# This file was developed with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: code generation
# Student contribution: high-level pseudocode, requirements definition
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
SecurePay API - FastAPI Backend for Fraud Analysis
===================================================
Provides REST API endpoints for the RAG-based fraud analyzer.

Usage:
    uvicorn app.backend.api:app --reload --port 8000
"""

import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from app.backend.rag_analyzer import analyze_scam, extract_query_patterns
from app.backend.search import search_scenarios
from app.backend.embeddings import CohereRateLimitError
from app.backend.db import get_connection
from app.backend.hierarchical_search import hierarchical_search, get_related_scenarios, multi_signal_search

# Initialize FastAPI app
app = FastAPI(
    title="SecurePay Fraud Analyzer",
    description="RAG-based UPI fraud detection and analysis",
    version="1.0.0"
)

# Mount static files (frontend)
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# Request/Response Models
class AnalyzeRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class RetrievedCase(BaseModel):
    rank: int
    similarity: float
    similarity_pct: str
    fraud_type: List[str]
    content_preview: str
    full_content: str


class AnalyzeResponse(BaseModel):
    query: str
    analysis: str
    retrieved_cases: List[RetrievedCase]
    model: str


class HealthResponse(BaseModel):
    status: str
    message: str


# Routes
@app.get("/", response_class=FileResponse)
async def serve_frontend():
    """Serve the main HTML page."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        raise HTTPException(status_code=404, detail="Frontend not found")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        message="SecurePay API is running"
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_fraud(request: AnalyzeRequest):
    """
    Analyze a potential fraud situation.

    - Retrieves similar cases from the database using semantic search
    - Passes context to LLM for constrained analysis
    - Returns analysis grounded in retrieved cases only
    """
    if not request.query or len(request.query.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 10 characters long"
        )

    try:
        result = analyze_scam(request.query, top_k=request.top_k)

        # Convert to response model
        retrieved_cases = [
            RetrievedCase(
                rank=case["rank"],
                similarity=case["similarity"],
                similarity_pct=case["similarity_pct"],
                fraud_type=case["fraud_type"] if isinstance(case["fraud_type"], list) else [case["fraud_type"]],
                content_preview=case["content_preview"],
                full_content=case["full_content"]
            )
            for case in result.get("retrieved_cases", [])
        ]

        return AnalyzeResponse(
            query=result["query"],
            analysis=result["analysis"],
            retrieved_cases=retrieved_cases,
            model=result["model"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_only(query: str, top_k: int = 5):
    """
    Search for similar fraud cases without LLM analysis.
    Useful for quick lookups.
    """
    if not query or len(query.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 5 characters long"
        )

    try:
        results = search_scenarios(query, top_k=top_k)

        cases = []
        for i, (scenario_id, raw_text, scenario_type, is_scam, similarity) in enumerate(results, 1):
            cases.append({
                "rank": i,
                "similarity": round(similarity, 4),
                "similarity_pct": f"{similarity:.1%}",
                "fraud_type": scenario_type,
                "content_preview": raw_text[:300] + "..." if len(raw_text) > 300 else raw_text,
                "full_content": raw_text
            })

        return {
            "query": query,
            "cases": cases
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Multi-Signal Search (Late Fusion with Weighted Scoring)
# =====================================================

class MultiSignalAnalyzeRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10
    weights: Optional[dict] = None  # {"canonical": 0.20, "type": 0.20, "mechanism": 0.35, "red_flag": 0.25}


@app.post("/api/analyze/multi-signal")
async def analyze_multi_signal(request: MultiSignalAnalyzeRequest):
    """
    Multi-signal search with weighted late fusion + LLM analysis.

    Extracts patterns (mechanisms, red flags, type) from the query,
    then searches using 4 signals with configurable weights:
    - canonical: raw_text embedding similarity (default 0.20)
    - type: exact type match (default 0.20)
    - mechanism: junction table overlap (default 0.35)
    - red_flag: junction table overlap (default 0.25)

    Returns:
    - extracted_patterns: The patterns extracted from the query (with names)
    - results: Ranked scenarios with score breakdown per signal
    - analysis: LLM analysis based on retrieved cases
    """
    if not request.query or len(request.query.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 10 characters long"
        )

    try:
        # Step 1: Extract patterns from query using LLM
        # Returns enriched patterns with IDs, names, descriptions, and embeddings
        patterns = extract_query_patterns(request.query)

        # Step 2: Enrich type info for display
        type_info = None
        if patterns.get("type"):
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT type_name FROM scenario_types WHERE type_id = %s", (patterns["type"],))
            row = cur.fetchone()
            if row:
                type_info = {"id": patterns["type"], "name": row[0].replace("_", " ").title()}
            cur.close()
            conn.close()

        # Build enriched patterns for display and analysis
        # Mechanisms and red flags already come enriched from extract_query_patterns
        enriched_patterns = {
            "type": type_info,
            "mechanisms": [
                {"name": m.get("name", "").replace("_", " ").title(), "description": m.get("description", "")}
                for m in patterns.get("mechanisms", [])
            ],
            "red_flags": [
                {"name": r.get("name", "").replace("_", " ").title(), "description": r.get("description", "")}
                for r in patterns.get("red_flags", [])
            ]
        }

        # Step 3: Multi-signal search with weighted fusion
        # Patterns include embeddings for mechanism/red flag similarity scoring
        results = multi_signal_search(
            query=request.query,
            patterns=patterns,
            weights=request.weights,
            top_k=request.top_k
        )

        # Step 4: LLM analysis using multi-signal results
        analysis_result = analyze_scam(request.query, results, enriched_patterns)

        return {
            "query": request.query,
            "extracted_patterns": enriched_patterns,
            "results": results,
            "analysis": analysis_result["analysis"],
            "model": analysis_result["model"],
            "weights": request.weights or {
                "canonical": 0.10,
                "type": 0.15,
                "mechanism": 0.40,
                "red_flag": 0.35
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Hierarchical Search Endpoints (4-Level Embeddings)
# =====================================================

class HierarchicalSearchRequest(BaseModel):
    query: str
    limits: Optional[dict] = None  # {"scenarios": 5, "types": 3, "mechanisms": 5, "red_flags": 5}


@app.post("/api/search/hierarchical")
async def search_hierarchical(request: HierarchicalSearchRequest):
    """
    4-Level Hierarchical Semantic Search.

    Searches across:
    - Level 1: Scenarios (raw_text embeddings)
    - Level 2: Scenario Types (taxonomy categories)
    - Level 3: Mechanisms (how scams work)
    - Level 4: Red Flags (warning signs)

    Returns results from all levels with similarity scores.
    """
    if not request.query or len(request.query.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 3 characters long"
        )

    try:
        results = hierarchical_search(request.query, request.limits)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/hierarchical")
async def search_hierarchical_get(query: str, limit: int = 5):
    """GET version of hierarchical search for simple queries."""
    if not query or len(query.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 3 characters long"
        )

    try:
        limits = {
            "scenarios": limit,
            "types": 3,
            "mechanisms": limit,
            "red_flags": limit
        }
        results = hierarchical_search(query, limits)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/related")
async def get_related(
    mechanism_id: Optional[str] = None,
    red_flag_id: Optional[str] = None,
    type_name: Optional[str] = None,
    limit: int = 10
):
    """
    Get scenarios related to a specific mechanism, red flag, or type.
    Use for drill-down from hierarchical search results.
    """
    if not mechanism_id and not red_flag_id and not type_name:
        raise HTTPException(
            status_code=400,
            detail="Must provide mechanism_id, red_flag_id, or type_name"
        )

    try:
        results = get_related_scenarios(
            mechanism_id=mechanism_id,
            red_flag_id=red_flag_id,
            type_name=type_name,
            limit=limit
        )
        return {"scenarios": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# =====================================================
# Awareness Chatbot Endpoints
# =====================================================

from app.backend.awareness_chatbot import chat_awareness


class AwarenessChatMessage(BaseModel):
    role: str
    content: str


class AwarenessChatRequest(BaseModel):
    message: str
    history: Optional[List[AwarenessChatMessage]] = []


@app.get("/awareness", response_class=FileResponse)
async def serve_awareness_page():
    """Serve the awareness chatbot HTML page."""
    awareness_path = frontend_path / "awareness.html"
    if awareness_path.exists():
        return FileResponse(str(awareness_path))
    else:
        raise HTTPException(status_code=404, detail="Awareness chatbot not found")


@app.post("/api/awareness/chat")
async def awareness_chat(request: AwarenessChatRequest):
    """Chat with the awareness chatbot about UPI fraud."""
    if not request.message or len(request.message.strip()) < 3:
        raise HTTPException(status_code=400, detail="Message must be at least 3 characters")

    try:
        history = [{"role": msg.role, "content": msg.content} for msg in (request.history or [])]
        result = chat_awareness(
            user_message=request.message,
            chat_history=history
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =====================================================
# Community Submissions Endpoints
# =====================================================

from app.backend.community import (
    submit_scam_story, list_submissions,
    search_submissions, get_submission_stats, review_submission
)


class SubmitScamRequest(BaseModel):
    incident_description: str
    scam_type: Optional[str] = None
    loss_amount: Optional[float] = None
    iocs: Optional[list] = []
    submitter_alias: Optional[str] = None


class SearchSubmissionsRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


@app.get("/community", response_class=FileResponse)
async def serve_community_page():
    """Serve the community submissions HTML page."""
    community_path = frontend_path / "community.html"
    if community_path.exists():
        return FileResponse(str(community_path))
    else:
        raise HTTPException(status_code=404, detail="Community page not found")


@app.post("/api/community/submit")
async def submit_community_scam(request: SubmitScamRequest):
    """Submit a new scam story with optional IOCs."""
    if not request.incident_description or len(request.incident_description.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Incident description must be at least 20 characters"
        )

    valid_ioc_types = {'upi_id', 'phone_number', 'url', 'telegram_id', 'email', 'app_name'}
    for ioc in (request.iocs or []):
        if ioc.get("type") not in valid_ioc_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid IOC type: {ioc.get('type')}. Must be one of {valid_ioc_types}"
            )

    try:
        submission_id = submit_scam_story(
            incident_description=request.incident_description.strip(),
            scam_type=request.scam_type,
            loss_amount=request.loss_amount,
            iocs=request.iocs,
            submitter_alias=request.submitter_alias
        )
        return {"success": True, "submission_id": submission_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/community/submissions")
async def get_community_submissions(
    status: Optional[str] = None,
    scam_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List community submissions with optional filters."""
    try:
        submissions = list_submissions(
            status=status, scam_type=scam_type,
            limit=limit, offset=offset
        )
        return {"submissions": submissions, "count": len(submissions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/community/search")
async def search_community_submissions(request: SearchSubmissionsRequest):
    """Semantic search over community submissions."""
    if not request.query or len(request.query.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Search query must be at least 5 characters"
        )
    try:
        results = search_submissions(request.query, top_k=request.top_k)
        return {"query": request.query, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/community/stats")
async def get_community_stats():
    """Get community submission statistics."""
    try:
        return get_submission_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/community/review/{submission_id}")
async def review_community_submission(submission_id: str, request: Request):
    """Update the status of a community submission to verified or rejected."""
    body = await request.json()
    status = body.get("status")
    if status not in ("verified", "rejected"):
        raise HTTPException(status_code=400, detail="status must be 'verified' or 'rejected'")
    try:
        sid = review_submission(submission_id, status)
        return {"success": True, "submission_id": sid, "status": status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

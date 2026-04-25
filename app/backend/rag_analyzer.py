# AI-Assisted Development Notice
# This file was developed by the student with AI used for code review (Anthropic, 2026).
# AI was used for: code review, syntax corrections, formatting, sentence construction, and prompt construction for LLM calls
# Student contribution: entire code written by student — architecture, implementation, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
RAG Analyzer - LLM Analysis on Retrieved Scenarios
===================================================
Retrieves similar fraud scenarios and uses Groq LLM to analyze.

Two-pass pattern extraction:
- Pass 1: LLM generates mechanism/red_flag descriptions
- Pass 2: LLM reviews and validates its own analysis
- Then: Embed descriptions → Find closest matches in DB (threshold 0.6)

Usage:
    python -m app.backend.rag_analyzer "Someone called saying my KYC expired..."
"""

import os
import sys
import json
import psycopg2
import cohere
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
import anthropic
from google import genai
from google.genai import types

from app.backend.search import search_scenarios

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/securepay")

# Initialize Anthropic client
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize Cohere client for embeddings
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY not found in environment variables")

co = cohere.Client(COHERE_API_KEY)

# Initialize Gemini client for Pass 1 (large context, 175K+ tokens)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Models
MODEL = "claude-haiku-4-5-20251001"  # Pass 2 + Analysis (small requests)
GEMINI_MODEL = "gemini-2.5-flash-lite"  # Pass 1 (large taxonomy, ~175K tokens)


def llm_generate_patterns(query: str, mechanisms_ref: list, red_flags_ref: list, types_ref: dict) -> dict:
    """
    Pass 1: LLM reads query + full taxonomy (names + descriptions), picks matching patterns.

    Args:
        query: User's description of a potential scam
        mechanisms_ref: List of dicts with id, name, description, scenario_count
        red_flags_ref: List of dicts with id, name, description, scenario_count
        types_ref: Dict of type_id -> type_name

    Returns:
        dict with type, mechanisms, red_flags (names + descriptions)
    """
    mech_lines = []
    for m in sorted(mechanisms_ref, key=lambda x: x["name"]):
        mech_lines.append(f"- {m['name']}: {m.get('description', '')}")
    mech_taxonomy = chr(10).join(mech_lines)

    rf_lines = []
    for r in sorted(red_flags_ref, key=lambda x: x["name"]):
        rf_lines.append(f"- {r['name']}: {r.get('description', '')}")
    rf_taxonomy = chr(10).join(rf_lines)

    prompt = f"""Analyze this potential scam description and identify patterns.

=== EXISTING TAXONOMY ===

MECHANISMS (scammer techniques — name: description):
{mech_taxonomy}

RED FLAGS (warning signs — name: description):
{rf_taxonomy}

AVAILABLE SCAM TYPES (pick one ID if applicable):
{json.dumps(types_ref, indent=2)}

=== RULES ===
1. Read through the existing taxonomy carefully. Prefer reusing existing names when the concept matches.
2. If you identify a genuinely new technique or warning sign not covered by ANY existing entry, create a new snake_case name and description.
3. Pick 1-3 mechanisms and 2-4 red flags that match what is described in the query.
4. Mechanisms = scammer's deceptive ACTIONS. Red flags = victim-observable WARNING SIGNS.

USER QUERY:
{query}

Return JSON only, no explanation:
{{
    "type": "type_id or null",
    "mechanisms": [
        {{"name": "existing_or_new_snake_case_name", "description": "Generic reusable description of how this technique works"}}
    ],
    "red_flags": [
        {{"name": "existing_or_new_snake_case_name", "description": "Generic reusable description of this warning sign"}}
    ]
}}
"""

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="You are a precise analyst of UPI fraud/scam patterns. You identify mechanisms and red flags using the provided taxonomy. Prefer reusing existing taxonomy names. If you find a genuinely novel pattern, create a new name. Return only valid JSON.",
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1000,
        ),
    )

    content = response.text.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"type": None, "mechanisms": [], "red_flags": []}


def llm_review_patterns(query: str, pass1_result: dict) -> dict:
    """
    Pass 2: LLM reviews its own analysis with verification checklist.

    Args:
        query: Original user query
        pass1_result: Output from Pass 1

    Returns:
        Validated/corrected dict with type, mechanisms, red_flags
    """
    prompt = f"""Review this pattern extraction for accuracy.

ORIGINAL QUERY:
{query}

PASS 1 ANALYSIS:
{json.dumps(pass1_result, indent=2)}

=== VERIFICATION CHECKLIST ===

For EACH mechanism:
1. Does it describe HOW the scam works (a scammer technique/action)?
2. Is there evidence in the query supporting it?
3. Is the description GENERIC and reusable (no specific names, platforms, amounts, roles)?
   BAD: "Scammer impersonated SBI bank officer" → FIX TO: "Scammer impersonated a trusted financial institution"
4. Is the name SHORT (2-4 words, snake_case)?

For EACH red flag:
1. Is it a WARNING SIGN observable BEFORE money was lost (not the scam itself)?
2. Is there evidence in the query?
3. Is the description GENERIC and reusable?
4. No overlap with mechanisms — different categories.

REMOVE items that:
- Contain speculation ("possibly", "likely", "might")
- Make logical leaps not stated in the query
- Cannot point to specific evidence in the query
- Overlap with another item (keep the stronger one)

Target: 1-3 mechanisms and 2-4 red flags. Remove the weakest if over these counts.

Return corrected JSON only, no explanation:
{{
    "type": "type_id or null",
    "mechanisms": [{{"name": "...", "description": "..."}}],
    "red_flags": [{{"name": "...", "description": "..."}}]
}}
"""

    response = client.messages.create(
        model=MODEL,
        system="You are a strict verifier of UPI fraud analysis. You remove anything fabricated, miscategorized, or redundant. You fix descriptions that are not generic. Return only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1000
    )

    content = response.content[0].text.strip()

    # Remove markdown code blocks if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fall back to pass1 result if parsing fails
        return pass1_result


def extract_query_patterns(query: str) -> dict:
    """
    Two-pass pattern extraction, then embed descriptions directly.

    Pass 1: LLM generates mechanism/red_flag names + descriptions (sees full taxonomy)
    Pass 2: LLM reviews and validates its own analysis
    Then: Embed descriptions with Cohere for multi-signal search

    Args:
        query: User's description of a potential scam situation

    Returns:
        dict with keys:
            type (ID),
            mechanisms (list of dicts with name, description, embedding),
            red_flags (list of dicts with name, description, embedding)
    """
    # Get reference taxonomy with descriptions
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT mechanism_id, mechanism_name, description, scenario_count FROM mechanisms")
    mechanisms_ref = [{"id": r[0], "name": r[1], "description": r[2], "scenario_count": r[3] or 0} for r in cur.fetchall()]

    cur.execute("SELECT red_flag_id, red_flag_name, description, scenario_count FROM red_flags")
    red_flags_ref = [{"id": r[0], "name": r[1], "description": r[2], "scenario_count": r[3] or 0} for r in cur.fetchall()]

    cur.execute("SELECT type_id, type_name FROM scenario_types")
    types_ref = {r[0]: r[1] for r in cur.fetchall()}

    cur.close()
    conn.close()

    # Pass 1: Generate patterns (Claude sees full taxonomy with descriptions)
    pass1_result = llm_generate_patterns(query, mechanisms_ref, red_flags_ref, types_ref)

    # Pass 2: Review and validate
    pass2_result = llm_review_patterns(query, pass1_result)

    # Validate type ID
    type_id = pass2_result.get("type")
    if type_id and type_id not in types_ref:
        type_id = None

    # Embed mechanism and red flag descriptions directly for multi-signal search
    mechanisms = pass2_result.get("mechanisms", [])
    red_flags = pass2_result.get("red_flags", [])

    mechs_with_names = [m for m in mechanisms if m.get("name")]
    rfs_with_names = [r for r in red_flags if r.get("name")]

    mech_descs = [m.get("description", m.get("name", "")) for m in mechs_with_names]
    rf_descs = [r.get("description", r.get("name", "")) for r in rfs_with_names]

    if mech_descs:
        try:
            mech_embeddings = co.embed(
                texts=mech_descs,
                model="embed-english-v3.0",
                input_type="search_document"
            ).embeddings
            for i, m in enumerate(mechs_with_names):
                m["embedding"] = mech_embeddings[i]
        except Exception as e:
            print(f"Error embedding mechanism descriptions: {e}")

    if rf_descs:
        try:
            rf_embeddings = co.embed(
                texts=rf_descs,
                model="embed-english-v3.0",
                input_type="search_document"
            ).embeddings
            for i, r in enumerate(rfs_with_names):
                r["embedding"] = rf_embeddings[i]
        except Exception as e:
            print(f"Error embedding red flag descriptions: {e}")

    return {
        "type": type_id,
        "mechanisms": mechanisms,
        "red_flags": red_flags
    }


def analyze_scam(user_query: str, results: list, enriched_patterns: dict) -> dict:
    """
    Analyze a potential scam situation using pre-computed multi-signal search results.

    Takes the already-retrieved cases and enriched patterns, fetches per-case
    mechanisms/red flags, and sends everything to Claude for analysis.

    Args:
        user_query: User's description of the situation
        results: Multi-signal search results (with score, breakdown, preview, scenario_type)
        enriched_patterns: Extracted query patterns with names/descriptions

    Returns:
        dict with analysis and model
    """
    if not results:
        return {
            "analysis": "No similar cases found in database.",
            "model": MODEL
        }

    # Fetch mechanisms and red flags for each matched case
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    context_parts = []
    for i, r in enumerate(results[:5], 1):
        sid = r.get("scenario_id")
        breakdown = r.get("breakdown", {})

        # Fetch case's mechanisms
        cur.execute("""
            SELECT m.mechanism_name, m.description
            FROM scenario_mechanisms sm JOIN mechanisms m USING(mechanism_id)
            WHERE sm.scenario_id = %s::uuid
        """, (sid,))
        case_mechs = [{"name": row[0], "description": row[1]} for row in cur.fetchall()]

        # Fetch case's red flags
        cur.execute("""
            SELECT rf.red_flag_name, rf.description
            FROM scenario_red_flags srf JOIN red_flags rf USING(red_flag_id)
            WHERE srf.scenario_id = %s::uuid
        """, (sid,))
        case_rfs = [{"name": row[0], "description": row[1]} for row in cur.fetchall()]

        # Format mechanisms
        mechs_text = "\n".join(
            f"  - {m['name']}: {m['description']}" for m in case_mechs
        ) if case_mechs else "  (none linked)"

        # Format red flags
        rfs_text = "\n".join(
            f"  - {rf['name']}: {rf['description']}" for rf in case_rfs
        ) if case_rfs else "  (none linked)"

        context_parts.append(f"""[CASE {i}]
Final Score: {r.get('score', 0):.1%}
Score Breakdown: Text={breakdown.get('canonical', 0):.0%}, Type={breakdown.get('type', 0):.0%}, Mechanism={breakdown.get('mechanism', 0):.0%}, RedFlag={breakdown.get('red_flag', 0):.0%}
Fraud Type: {r.get('scenario_type', 'unknown')}
Content: {r.get('preview', '')}
Mechanisms:
{mechs_text}
Red Flags:
{rfs_text}
""")

    cur.close()
    conn.close()

    context = "\n".join(context_parts)

    # Format query's extracted patterns
    query_type = enriched_patterns.get("type")
    query_type_text = f"{query_type['name']}" if query_type else "Not identified"

    query_mechs = enriched_patterns.get("mechanisms", [])
    query_mechs_text = "\n".join(
        f"  - {m['name']}: {m['description']}" for m in query_mechs
    ) if query_mechs else "  (none extracted)"

    query_rfs = enriched_patterns.get("red_flags", [])
    query_rfs_text = "\n".join(
        f"  - {rf['name']}: {rf['description']}" for rf in query_rfs
    ) if query_rfs else "  (none extracted)"

    prompt = f"""Analyze this potential fraud situation by comparing it against the retrieved database cases.

USER'S SITUATION:
{user_query}

PATTERNS EXTRACTED FROM USER'S QUERY:
Type: {query_type_text}
Mechanisms:
{query_mechs_text}
Red Flags:
{query_rfs_text}

SCORING METHOD:
Cases are ranked by a weighted fusion of 4 signals:
- Text Similarity (10%): How similar the raw text is to the query (embedding cosine similarity)
- Type Match (15%): Whether the fraud type matches (1.0 if match, 0 if not)
- Mechanism Similarity (40%): Embedding similarity between query's mechanism descriptions and case's mechanism descriptions (avg of best matches)
- Red Flag Similarity (35%): Embedding similarity between query's red flag descriptions and case's red flag descriptions (avg of best matches)

RETRIEVED DATABASE CASES:
{context}

STRICT RULES:
1. ONLY use information from the provided cases and extracted patterns
2. Do NOT use any external knowledge
3. Reference specific cases by number and cite their mechanisms/red flags
4. Do NOT invent information not present in the cases
5. Do NOT give advice or recommendations. Only report patterns and risks.

ANALYSIS FORMAT:
1. **MATCHING CASES**: Which cases match and why? Reference their mechanisms and red flags.
2. **COMMON PATTERNS**: What mechanisms and red flags appear across multiple cases? Show which cases share which patterns.
3. **FRAUD TYPE**: Based on the case labels and extracted patterns, what type of fraud is this?
4. **RISK INDICATORS**: What specific red flags from the matched cases are present in the user's situation?
5. **CONFIDENCE**: How well do the retrieved cases match? (High/Medium/Low/No Match). Use the score breakdowns to explain."""

    response = client.messages.create(
        model=MODEL,
        system="You are a fraud pattern analysis system. You identify and report patterns and risks by comparing situations against a database of known fraud cases. You reference specific cases, mechanisms, and red flags. You never give advice or recommendations. You never use external knowledge — only what is provided.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1500
    )

    return {
        "analysis": response.content[0].text,
        "model": MODEL
    }


def main():
    """Interactive mode or command line usage."""
    import argparse
    from app.backend.hierarchical_search import multi_signal_search

    parser = argparse.ArgumentParser(description="Analyze potential scam situations")
    parser.add_argument("query", nargs="?", help="Scam situation to analyze")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of similar cases to retrieve")

    args = parser.parse_args()

    def run_query(query, top_k=5):
        patterns = extract_query_patterns(query)
        results = multi_signal_search(query=query, patterns=patterns, top_k=top_k)
        enriched = {
            "type": {"name": patterns["type"]} if patterns.get("type") else None,
            "mechanisms": [{"name": m.get("name", ""), "description": m.get("description", "")} for m in patterns.get("mechanisms", [])],
            "red_flags": [{"name": r.get("name", ""), "description": r.get("description", "")} for r in patterns.get("red_flags", [])]
        }
        return analyze_scam(query, results, enriched)

    if args.query:
        result = run_query(args.query, top_k=args.top_k)
        print_result(result)
    else:
        print("=" * 70)
        print("SECUREPAY RAG ANALYZER")
        print("Describe a situation and I'll analyze if it's a scam")
        print("Type 'quit' to exit")
        print("=" * 70)

        while True:
            print("\n")
            query = input("Describe the situation: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break

            if not query:
                continue

            print("\nAnalyzing...\n")
            result = run_query(query, top_k=args.top_k)
            print_result(result)


def print_result(result: dict):
    """Pretty print the analysis result."""
    print("=" * 70)
    print("ANALYSIS RESULT")
    print("=" * 70)

    print("\n" + result["analysis"])

    print("\n" + "-" * 70)
    print("RETRIEVED CASES:")
    print("-" * 70)

    for case in result.get("retrieved_cases", []):
        print(f"\n#{case['rank']} | Similarity: {case['similarity_pct']} | Type: {case['fraud_type']}")
        print(f"   {case['content_preview'][:150]}...")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

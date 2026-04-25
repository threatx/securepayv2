# AI-Assisted Development Notice
# This file was developed by the student with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: writing LLM prompts
# Student contribution: core implementation, architecture, RAG pipeline design, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

"""
Awareness Chatbot - RAG + Claude Haiku for UPI Fraud Education
==============================================================
Retrieves relevant awareness content, passes to Claude Haiku
for educational responses about UPI fraud.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import anthropic
from dotenv import load_dotenv
from app.backend.awareness_search import search_awareness
from app.backend.search import search_scenarios

load_dotenv()

anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"


SYSTEM_PROMPT_TEMPLATE = """You are SecurePay Assistant, an educational chatbot about UPI (Unified Payments Interface) fraud in India.

Your purpose is to help people understand:
- How different UPI scams work
- How to identify and avoid scams
- What to do if they have been scammed
- General UPI safety practices

RULES:
1. Base your answers ONLY on the provided context documents below. If the context doesn't cover the topic, say so honestly.
2. Be educational and clear. Use simple language.
3. When explaining a scam type, describe the step-by-step mechanism so users can recognize it.
4. Always include practical prevention tips when relevant.
5. If someone describes being scammed, provide actionable recovery steps (file complaint at cybercrime.gov.in, contact bank within 24 hours, etc.)
6. Do NOT provide legal advice. Direct users to appropriate authorities.
7. Keep responses concise but thorough.
8. Cite the source titles when referencing specific information.

CONTEXT DOCUMENTS:
{awareness_context}

REAL-WORLD EXAMPLES:
{scenario_context}"""


def format_awareness_context(results: list) -> str:
    """Format awareness search results into context string."""
    if not results:
        return "No relevant awareness content found."

    parts = []
    for i, r in enumerate(results, 1):
        title = r[1] or "Untitled"
        content = r[2][:500] if r[2] else ""
        ctype = r[3] or "unknown"
        similarity = r[6]
        parts.append(f"[DOC {i}] Title: \"{title[:80]}\" | Type: {ctype} | Relevance: {similarity:.0%}\n{content}")

    return "\n\n".join(parts)


def format_scenario_context(results: list) -> str:
    """Format scenario search results into context string."""
    if not results:
        return "No relevant examples found."

    parts = []
    for i, r in enumerate(results, 1):
        text = r[1][:400] if r[1] else ""
        stype = r[2] or "unknown"
        similarity = r[4]
        parts.append(f"[EXAMPLE {i}] Type: {stype} | Relevance: {similarity:.0%}\n{text}")

    return "\n\n".join(parts)


def chat_awareness(user_message: str, chat_history: list = None, top_k_awareness: int = 5, top_k_scenarios: int = 3) -> dict:
    """
    Process a chat message with RAG retrieval and Claude Haiku.

    Args:
        user_message: The user's question
        chat_history: List of {"role": "user"|"assistant", "content": "..."} dicts
        top_k_awareness: Number of awareness docs to retrieve
        top_k_scenarios: Number of scenario examples to retrieve

    Returns:
        {"response": str, "sources": list, "model": str}
    """
    if chat_history is None:
        chat_history = []

    # RAG retrieval
    awareness_results = search_awareness(user_message, top_k=top_k_awareness)
    scenario_results = search_scenarios(user_message, top_k=top_k_scenarios)

    # Build system prompt with context
    awareness_context = format_awareness_context(awareness_results)
    scenario_context = format_scenario_context(scenario_results)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        awareness_context=awareness_context,
        scenario_context=scenario_context
    )

    # Build messages array (system is separate in Anthropic API)
    messages = []

    # Add recent chat history (limit to last 10 messages)
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Call Claude Haiku
    response = anthropic_client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=messages
    )

    clean_response = response.content[0].text

    # Build sources list
    sources = []
    for r in awareness_results:
        sources.append({
            "title": (r[1] or "Untitled")[:80],
            "type": r[3],
            "similarity": round(r[6], 3)
        })

    return {
        "response": clean_response,
        "sources": sources,
        "model": MODEL
    }


if __name__ == "__main__":
    print("Testing awareness chatbot...")
    print("=" * 60)
    result = chat_awareness("How do QR code scams work?")
    print(f"Response:\n{result['response']}")
    print(f"\nSources: {[s['title'][:40] for s in result['sources']]}")
    print(f"Model: {result['model']}")

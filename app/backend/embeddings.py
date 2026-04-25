# AI-Assisted Development Notice
# This file was developed by the student with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: adding comments and error handling
# Student contribution: core implementation, architecture, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

import os
import cohere
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Cohere client
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY not found in environment variables")

co = cohere.Client(COHERE_API_KEY)

# Model configuration
MODEL = "embed-english-v3.0"
EMBEDDING_DIM = 1024  # Cohere v3 dimension


class CohereRateLimitError(Exception):
    """Raised when Cohere API rate limit (429) is hit."""
    pass


def get_embedding(text: str, input_type: str = "search_document") -> list:
    """
    Generate embedding for text using Cohere embed-v3.

    Args:
        text: Text to embed
        input_type: "search_document" for DB storage, "search_query" for queries

    Returns:
        List of floats (1024 dimensions)

    Raises:
        CohereRateLimitError: When API rate limit (429) is hit
    """
    try:
        response = co.embed(
            texts=[text],
            model=MODEL,
            input_type=input_type
        )
        return response.embeddings[0]
    except cohere.TooManyRequestsError as e:
        raise CohereRateLimitError(
            "Cohere API rate limit reached (1000 calls/month on Trial key). "
            "Please upgrade your API key or wait for monthly reset."
        ) from e


def get_query_embedding(text: str) -> list:
    """Get embedding optimized for search queries."""
    return get_embedding(text, input_type="search_query")


def get_document_embedding(text: str) -> list:
    """Get embedding optimized for document storage."""
    return get_embedding(text, input_type="search_document")


def get_embeddings_batch(texts: list, input_type: str = "search_document") -> list:
    """
    Generate embeddings for multiple texts in one API call.

    Args:
        texts: List of texts to embed
        input_type: "search_document" or "search_query"

    Returns:
        List of embeddings (each 1024 dimensions)

    Raises:
        CohereRateLimitError: When API rate limit (429) is hit
    """
    # Cohere API has a limit of 96 texts per call
    BATCH_SIZE = 96
    all_embeddings = []

    try:
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            response = co.embed(
                texts=batch,
                model=MODEL,
                input_type=input_type
            )
            all_embeddings.extend(response.embeddings)
    except cohere.TooManyRequestsError as e:
        raise CohereRateLimitError(
            "Cohere API rate limit reached (1000 calls/month on Trial key). "
            "Please upgrade your API key or wait for monthly reset."
        ) from e

    return all_embeddings

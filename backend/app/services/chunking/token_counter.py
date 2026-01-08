"""Token counting utilities using tiktoken.

Provides accurate token counting for OpenAI-compatible models
using the cl100k_base encoding (GPT-4, text-embedding-ada-002).
"""

from functools import lru_cache

import tiktoken


@lru_cache(maxsize=4)
def get_encoder(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    """Get cached tiktoken encoder.

    Args:
        encoding_name: tiktoken encoding name. Defaults to cl100k_base
                      which is used by GPT-4 and embedding models.

    Returns:
        Cached tiktoken Encoding instance.
    """
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for.
        encoding_name: tiktoken encoding name. Defaults to cl100k_base.

    Returns:
        Number of tokens in the text.
    """
    if not text:
        return 0

    encoder = get_encoder(encoding_name)
    return len(encoder.encode(text))


def estimate_tokens_fast(text: str) -> int:
    """Fast token estimation without tiktoken.

    Useful for rough estimates when tiktoken overhead is too high.
    Uses the ~4 characters per token heuristic for English text.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated number of tokens.
    """
    if not text:
        return 0

    # Rough estimate: ~4 characters per token for English
    # Slightly more conservative for legal text with longer words
    return len(text) // 4

"""Acts library modules."""

from .indexer import ActsIndexer, index_acts
from .verifier import ActsVerifier, verify_citation
from .india_code import IndiaCodeClient

__all__ = [
    "ActsIndexer",
    "index_acts",
    "ActsVerifier",
    "verify_citation",
    "IndiaCodeClient",
]

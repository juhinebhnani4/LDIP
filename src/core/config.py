"""Configuration management for Jaanch Lite."""

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    vision_agent_api_key: str = ""  # Landing AI ADE
    voyage_api_key: str = ""        # Voyage AI
    google_api_key: str = ""        # Google Gemini (cheapest for extraction)
    openai_api_key: str = ""        # OpenAI (alternative)
    anthropic_api_key: str = ""     # Anthropic (optional)

    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    chroma_db_path: Path = Path("./vectordb")
    acts_db_path: Path = Path("./vectordb/acts")
    docs_db_path: Path = Path("./vectordb/documents")
    data_path: Path = Path("./data")

    # Voyage AI Models
    embedding_model: str = "voyage-law-2"      # Legal-specific embeddings
    rerank_model: str = "rerank-2.5"           # Instruction-following reranker

    # LLM for Extraction (Instructor)
    extraction_provider: str = "gemini"        # "gemini" or "openai"
    extraction_model: str = "models/gemini-2.5-flash"  # Best reasoning + structured output

    # Search Settings
    search_top_k: int = 20          # Initial retrieval
    rerank_top_k: int = 5           # After reranking
    similarity_threshold: float = 0.3

    # Citation Extraction
    use_llm_extraction: bool = False  # Set True if you have OpenAI key
    regex_only_mode: bool = True      # Default to regex-only (no OpenAI needed)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

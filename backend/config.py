"""
Configuration management for RazorSearch backend
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""
    
    # LLM Configuration
    LLM_AZURE_ENDPOINT: str = os.getenv("LLM_AZURE_ENDPOINT", "https://fy26-hackon-q3.openai.azure.com/")
    LLM_AZURE_API_KEY: Optional[str] = os.getenv("LLM_AZURE_API_KEY")
    LLM_AZURE_API_VERSION: str = os.getenv("LLM_AZURE_API_VERSION", "2024-12-01-preview")
    LLM_DEPLOYMENT: str = os.getenv("LLM_DEPLOYMENT", "fy26-hackon-q3-gpt-4.1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1")
    
    # Embedding Configuration
    EMBEDDING_AZURE_ENDPOINT: str = os.getenv("EMBEDDING_AZURE_ENDPOINT", "https://fy26-hackon-q3.openai.azure.com/")
    EMBEDDING_AZURE_API_KEY: Optional[str] = os.getenv("EMBEDDING_AZURE_API_KEY")
    EMBEDDING_AZURE_API_VERSION: str = os.getenv("EMBEDDING_AZURE_API_VERSION", "2024-12-01-preview")
    EMBEDDING_DEPLOYMENT: str = os.getenv("EMBEDDING_DEPLOYMENT", "fy26-hackon-q3-gpt-4.1")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    # SSL Configuration (set to "false" only if you have SSL certificate issues - not recommended for production)
    VERIFY_SSL: bool = os.getenv("VERIFY_SSL", "true").lower() != "false"
    
    # Vector Database Configuration
    VECTOR_DB_PROVIDER: str = os.getenv("VECTOR_DB_PROVIDER", "qdrant")  # qdrant
    # Qdrant Configuration
    # Two modes supported:
    # 1. Local server (Docker): Set QDRANT_URL=http://localhost:6333 (no API key needed)
    # 2. Cloud: Set QDRANT_URL=https://your-cluster.qdrant.io and QDRANT_API_KEY
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", "http://localhost:6333")  # Qdrant server URL (required)
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")  # For cloud mode only
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "razorsearch")
    
    # Search Configuration
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    MIN_SIMILARITY_SCORE: float = float(os.getenv("MIN_SIMILARITY_SCORE", "0.5"))
    ENABLE_QUERY_ENRICHMENT: bool = os.getenv("ENABLE_QUERY_ENRICHMENT", "true").lower() == "true"
    
    # Cache Configuration
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "false").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # seconds


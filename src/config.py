# src/config.py

"""
Configuration module for RAG application.

This module handles all application configuration with proper validation,
type checking, and environment variable management.
"""

import os
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logger = logging.getLogger(__name__)


def find_project_root(marker_file: str = ".env") -> Path:
    """
    Find the project root by searching for a marker file.
    
    Args:
        marker_file: File to search for (default: .env)
        
    Returns:
        Path to the project root directory
        
    Raises:
        FileNotFoundError: If marker file is not found
    """
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / marker_file).exists():
            return parent
    
    # Fallback to parent directory if .env not found
    logger.warning(f"{marker_file} not found, using parent directory")
    return Path(__file__).resolve().parent.parent


# Load environment variables
try:
    project_root = find_project_root()
    env_path = project_root / ".env"
    load_dotenv(env_path)
    logger.info(f"Loaded environment variables from {env_path}")
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")


class VectorStoreSettings(BaseSettings):
    """Configuration for the vector store (Qdrant)."""
    
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        case_sensitive=False,
        extra="ignore"
    )
    
    collection_name: str = Field(
        default="rag_documents",
        description="Name of the Qdrant collection",
        min_length=1
    )
    api_key: str = Field(
        ...,  # Required field
        description="API key for Qdrant",
        min_length=1
    )
    port: int = Field(
        default=6333,
        description="Port for Qdrant",
        ge=1,
        le=65535
    )
    host: str = Field(
        default="http://localhost",
        description="Host URL for Qdrant",
        min_length=1
    )
    vector_size: int = Field(
        default=3072,
        description="Dimension of the embedding vectors",
        gt=0
    )
    distance_metric: Literal["COSINE", "DOT", "EUCLID"] = Field(
        default="COSINE",
        description="Distance metric for vector similarity"
    )
    timeout: int = Field(
        default=30,
        description="Connection timeout in seconds",
        gt=0
    )
    
    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Strips the protocol off the host if present."""
        v = v.strip()
        
        # Strip common protocols if they exist
        if v.startswith("http://"):
            v = v[len("http://"):]
        elif v.startswith("https://"):
            v = v[len("https://"):]

        return v.rstrip("/")
    
    @model_validator(mode="after")
    def validate_settings(self):
        """Additional validation after model creation"""
        logger.info(f"Vector store configured: {self.host}:{self.port}/{self.collection_name}")
        return self


class LLMSettings(BaseSettings):
    """Configuration for the LLM (Gemini)."""
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )
    
    model_name: str = Field(
        default="gemini-1.5-flash",
        description="Name of the Gemini model to use",
        alias="GEMINI_MODEL"
    )
    api_key: str = Field(
        ...,  # Required field
        description="API key for Google AI platform",
        alias="GOOGLE_API_KEY",
        min_length=1
    )
    temperature: float = Field(
        default=0.7,
        description="Sampling temperature for generation",
        ge=0.0,
        le=2.0
    )
    max_tokens: Optional[int] = Field(
        default=2048,
        description="Maximum tokens to generate",
        gt=0
    )
    timeout: int = Field(
        default=60,
        description="API timeout in seconds",
        gt=0
    )
    
    @model_validator(mode="after")
    def validate_settings(self):
        """Log configuration"""
        logger.info(f"LLM configured: {self.model_name}")
        return self


class EmbeddingSettings(BaseSettings):
    """Configuration for the embedding model."""
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )
    
    model_name: str = Field(
        default="models/embedding-001",
        description="Name of the embedding model to use",
        alias="EMBEDDING_MODEL"
    )
    batch_size: int = Field(
        default=100,
        description="Batch size for embedding generation",
        gt=0,
        le=1000
    )
    timeout: int = Field(
        default=30,
        description="API timeout in seconds",
        gt=0
    )
    
    @model_validator(mode="after")
    def validate_settings(self):
        """Log configuration"""
        logger.info(f"Embedding model configured: {self.model_name}")
        return self


class RerankerSettings(BaseSettings):
    """Configuration for the reranking process."""
    
    model_config = SettingsConfigDict(
        env_prefix="RERANKER_",
        case_sensitive=False,
        extra="ignore"
    )
    
    model: str = Field(
        default="rerank-english-v3.0",
        description="Name of the reranker model"
    )
    cohere_api_key: Optional[str] = Field(
        default=None,
        description="API key for Cohere (if using Cohere reranker)",
        alias="COHERE_API_KEY"
    )
    top_k: int = Field(
        default=10,
        description="Number of top results to return after reranking",
        gt=0,
        le=100
    )
    enabled: bool = Field(
        default=True,
        description="Whether reranking is enabled"
    )
    
    @model_validator(mode="after")
    def validate_cohere_settings(self):
        """Validate Cohere-specific settings"""
        if self.enabled and "cohere" in self.model.lower() and not self.cohere_api_key:
            raise ValueError("COHERE_API_KEY required when using Cohere reranker")
        return self


class IngestionSettings(BaseSettings):
    """Configuration for the data ingestion pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        case_sensitive=False,
        extra="ignore"
    )

    chunk_size: int = Field(
        default=1024,
        description="The size of text chunks for splitting documents."
    )
    chunk_overlap: int = Field(
        default=128,
        description="The overlap between consecutive text chunks."
    )
    embedding_batch_size: int = Field(
        default=32,
        description="The number of chunks to process in a single embedding batch."
    )

class RetrieverSettings(BaseSettings):
    """Configuration for the document retriever."""
    
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVER_",
        case_sensitive=False,
        extra="ignore"
    )
    
    top_k: int = Field(
        default=5,
        description="Number of documents to retrieve",
        gt=0
    )
    
    @model_validator(mode="after")
    def validate_settings(self):
        """Log configuration"""
        logger.info(f"Retriever configured with top_k={self.top_k}")
        return self
    
class AppSettings(BaseSettings):
    """Main application settings container."""
    
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )
    
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
        alias="ENVIRONMENT"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
        alias="DEBUG"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        alias="LOG_LEVEL"
    )
    
    # Nested settings
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    retriever: RetrieverSettings = Field(default_factory=RetrieverSettings)


@lru_cache()
def get_settings() -> AppSettings:
    """
    Get cached application settings.
    
    This function is cached to ensure settings are loaded only once.
    Use this function throughout your application to access configuration.
    
    Returns:
        AppSettings: Application configuration object
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.llm.model_name)
        gemini-1.5-flash
    """
    try:
        settings = AppSettings()
        logger.info("Settings loaded successfully")
        return settings
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        raise

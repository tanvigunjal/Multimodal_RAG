# src/core/retriever.py

from __future__ import annotations
from typing import Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import FieldCondition, MatchValue
from langchain_qdrant import QdrantVectorStore
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

from src.config import get_settings
from src.ingestion.adapter import LangChainEmbeddingsAdapter
from src.services.embedding_service import embedding_service
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _qdrant_client_from_settings() -> QdrantClient:
    s = get_settings().vector_store
    host = s.host.replace("http://", "").replace("https://", "")  # qdrant_client expects bare host
    client = QdrantClient(
        host=host,
        port=s.port,
        api_key=s.api_key,
        timeout=s.timeout,
    )
    return client


def build_vectorstore() -> QdrantVectorStore:
    settings = get_settings()
    client = _qdrant_client_from_settings()
    collection_name = settings.vector_store.collection_name

    # Use the centralized, batch-capable embedding service
    embeddings = LangChainEmbeddingsAdapter(embedding_service)

    # Check if the collection exists. If not, create it.
    try:
        client.get_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' already exists.")
    except Exception:
        logger.info(f"Collection '{collection_name}' not found. Creating it now.")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.embeddings.embedding_dim,
                distance=models.Distance.COSINE
            ),
        )
        logger.info(f"Successfully created collection '{collection_name}'.")

    vs = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        retrieval_mode="dense"
    )
    return vs


def build_retriever(content_type_preference: Optional[str] = None):
    """
    Returns a LangChain retriever that:
      1) pulls k candidates from Qdrant, optionally filtered by chunk_type
      2) reranks them using Cohere
      3) returns top_n reranked docs
    """
    settings = get_settings()

    # If the user asks for a specific content type, build a Qdrant filter.
    # This is pushed down to the vector DB for efficient retrieval.
    search_kwargs = {"k": settings.reranker.top_k or 10}
    if content_type_preference:
        logger.info(f"Retriever: Filtering for chunk_type='{content_type_preference}'")
        search_kwargs["filter"] = FieldCondition(
            key="metadata.chunk_type",
            match=MatchValue(value=content_type_preference),
        )

    vectorstore = build_vectorstore()
    base_retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)

    # Cohere Reranker as a document compressor
    compressor = CohereRerank(
        cohere_api_key=settings.reranker.cohere_api_key,
        model=settings.reranker.model,
        top_n=settings.reranker.top_k if settings.reranker.top_k <= 50 else 10,
    )

    retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever,
    )
    return retriever

# src/ingestion/vector_manager.py

import uuid
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

from src.ingestion.adapter import LangChainEmbeddingsAdapter
from src.services.embedding_service import EmbeddingService
from src.services.vectordb_service import VectorDBService
from src.utils.logger import get_logger

logger = get_logger(__name__)

class VectorStoreManager:
    """Manages the embedding and ingestion of documents into a vector store."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vectordb_service: VectorDBService,
    ):
        self.embedding_service = embedding_service
        self.vectordb_service = vectordb_service
        self.embeddings = LangChainEmbeddingsAdapter(self.embedding_service)
        self.vector_store = QdrantVectorStore(
            client=self.vectordb_service.client,
            collection_name=self.vectordb_service.collection_name,
            embedding=self.embeddings,
        )

    def add_chunks(self, document_chunks: List[Dict[str, Any]]):
        """Converts chunk dictionaries to Documents and adds them to the vector store."""
        if not document_chunks:
            logger.warning("No chunks provided to add to the vector store.")
            return

        # Convert dictionaries to LangChain Document objects and flatten metadata
        langchain_docs: List[Document] = []
        for chunk in document_chunks:
            metadata = {
                **chunk.get("document_metadata", {}),
                **chunk.get("structural_metadata", {}),
                **chunk.get("multimodal_metadata", {}),
                "chunk_id": chunk.get("chunk_id"),
            }
            # Clean up nested structures for top-level access in Qdrant
            metadata.pop("document_metadata", None)
            metadata.pop("structural_metadata", None)
            metadata.pop("multimodal_metadata", None)
            
            langchain_docs.append(
                Document(page_content=chunk.get("raw_content", ""), metadata=metadata)
            )

        ids = [str(uuid.uuid4()) for _ in langchain_docs]
        
        # LangChain handles batching and embedding via the adapter
        self.vector_store.add_documents(documents=langchain_docs, ids=ids)
        logger.info(f"Successfully ingested {len(langchain_docs)} chunks into Qdrant.")

    def is_document_processed(self, file_path: str) -> bool:
        """Checks if a document with the given file_path already exists."""
        try:
            res, _ = self.vectordb_service.client.scroll(
                collection_name=self.vectordb_service.collection_name,
                scroll_filter=Filter(must=[FieldCondition(key="file_name", match=MatchValue(value=file_path))]),
                limit=1,
            )
            return bool(res)
        except Exception as e:
            logger.error(f"Failed to check if document is processed: {e}", exc_info=True)
            return False

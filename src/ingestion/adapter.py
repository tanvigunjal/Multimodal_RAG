
# You will need an adapter file for the embeddings as well
# src/ingestion/adapter.py
from typing import List
from langchain_core.embeddings import Embeddings
from src.services.embedding_service import EmbeddingService

class LangChainEmbeddingsAdapter(Embeddings):
    def __init__(self, service: EmbeddingService):
        self.service = service
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.service.generate_embeddings(texts, task_type="retrieval_document")
    def embed_query(self, text: str) -> List[float]:
        return self.service.generate_embeddings(text, task_type="retrieval_query")
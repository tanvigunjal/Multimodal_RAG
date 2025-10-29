# src/services/embedding_service.py

import time
from typing import List, Union, Literal, Iterable

import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

TaskType = Literal["retrieval_document", "retrieval_query", "semantic_similarity"]


def _chunk_iter(seq: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


class EmbeddingService:
    """
    A service for generating embeddings using Google's Generative AI.

    Singleton to avoid repeated client setup.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        try:
            self.settings = get_settings()
            self.model_name = self.settings.embedding.model_name
            self.batch_size = self.settings.embedding.batch_size

            # Configure the generative AI client
            genai.configure(api_key=self.settings.llm.api_key)

            # Optional: fast sanity check (will no-op if not supported in your SDK)
            try:
                _ = genai.get_model(self.model_name)
            except Exception:
                # Fallback: allow proceed; many SDK versions don’t expose get_model for embeddings
                pass

            logger.info(f"EmbeddingService initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _embed_batch(self, texts: List[str], task_type: TaskType) -> List[List[float]]:
        """Embed a batch of strings and return a list of vectors."""
        result = genai.embed_content(
            model=self.model_name,
            content=texts,
            task_type=task_type,
        )
        # SDK returns {'embedding': [[...], [...]]} for batched input
        vecs = result.get("embedding")
        if not isinstance(vecs, list) or not all(isinstance(v, list) for v in vecs):
            raise RuntimeError("Embedding API returned unexpected shape for batch input.")
        return vecs

    def generate_embeddings(
        self,
        content: Union[str, List[str]],
        task_type: TaskType,
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for a string or list of strings.
        Returns a single vector for str, or a list of vectors for List[str].
        """
        if isinstance(content, dict):
            content = content.get("input", "")
            
        if not content:
            raise ValueError("Input content cannot be empty.")
        if not task_type:
            raise ValueError("Task type must be specified.")

        is_single_string = isinstance(content, str)
        texts = [content] if is_single_string else content

        logger.info(
            f"Generating embeddings (model={self.model_name}, task={task_type}, "
            f"items={len(texts)})"
        )

        # Process in batches
        all_vectors: List[List[float]] = []
        for batch in _chunk_iter(texts, self.batch_size):
            batch_vecs = self._embed_batch(batch, task_type)
            all_vectors.extend(batch_vecs)

        logger.info("Successfully generated embeddings.")

        # Return single vector if input was a single string
        return all_vectors[0] if is_single_string else all_vectors


# Singleton instance
embedding_service = EmbeddingService()

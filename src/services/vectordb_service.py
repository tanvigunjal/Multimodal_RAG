# src/services/vectordb_service.py

from typing import List, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, UpdateStatus
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VectorDBService:
    """
    Singleton for interacting with the Qdrant vector database.
    Ensures the collection and required payload indexes are created.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorDBService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        try:
            self.settings = get_settings().vector_store

            # QdrantClient expects host without scheme for host+port init
            host = self.settings.host.replace("http://", "").replace("https://", "")
            self.client = QdrantClient(
                host=host,
                port=self.settings.port,
                api_key=self.settings.api_key,
                timeout=self.settings.timeout,
            )
            self.collection_name = self.settings.collection_name

            self._create_collection_if_not_exists()
            logger.info("VectorDBService initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize VectorDBService: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _create_collection_if_not_exists(self):
        """Create the collection if missing and ensure payload indexes."""
        try:
            self.client.get_collection(collection_name=self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists.")
            self._create_required_indices()
        except Exception:
            logger.info(f"Creating collection: {self.collection_name}")
            distance_map = {
                "COSINE": models.Distance.COSINE,
                "DOT": models.Distance.DOT,
                "EUCLID": models.Distance.EUCLID,
            }
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.settings.vector_size,            # must match embedding dim
                    distance=distance_map[self.settings.distance_metric],
                ),
            )
            logger.info(f"Collection '{self.collection_name}' created successfully.")
            self._create_required_indices()

    def _create_required_indices(self):
        """
        Create payload indexes for hot filter keys (flattened).
        Add or remove as needed for your queries.
        """
        to_index = [
            ("file_path", models.PayloadSchemaType.KEYWORD),
            ("modality", models.PayloadSchemaType.KEYWORD),
            ("element_type", models.PayloadSchemaType.KEYWORD),
            ("page_number", models.PayloadSchemaType.INTEGER),
            ("chunk_id", models.PayloadSchemaType.KEYWORD),
            ("figure_id", models.PayloadSchemaType.KEYWORD),
        ]
        for field_name, schema in to_index:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
                logger.info(f"Ensured index on '{field_name}'.")
            except Exception as e:
                # benign if already exists
                logger.debug(f"Index on '{field_name}' may already exist: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def upsert_points(self, points: List[PointStruct]) -> dict:
        """
        If you still upsert manually somewhere, keep this util.
        Not used by the LangChain path, but harmless to keep.
        """
        if not points:
            raise ValueError("Points list cannot be empty.")
        try:
            logger.info(f"Upserting {len(points)} points into '{self.collection_name}'...")
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                wait=True,
                points=points,
            )
            logger.info("Successfully upserted points.")
            return operation_info
        except Exception as e:
            logger.error(f"Failed to upsert points: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> List[models.ScoredPoint]:
        """Low-level search helper (optional)."""
        try:
            logger.info(f"Searching '{self.collection_name}'...")
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
            logger.info(f"Search completed. Found {len(search_result)} results.")
            return search_result
        except Exception as e:
            logger.error(f"Failed to perform search: {e}")
            raise


# Singleton instance
vectordb_service = VectorDBService()

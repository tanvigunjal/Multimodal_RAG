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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _initialize(self):
        """Initialize the VectorDBService with retry logic"""
        try:
            self.settings = get_settings().vector_store

            # QdrantClient expects host without scheme for host+port init
            host = self.settings.host.replace("http://", "").replace("https://", "")
            
            logger.info(f"Connecting to Qdrant at {host}:{self.settings.port}")
            self.client = QdrantClient(
                host=host,
                port=self.settings.port,
                api_key=self.settings.api_key,
                timeout=self.settings.timeout,
            )
            self.collection_name = self.settings.collection_name

            # Verify connection
            self.client.get_collections()
            logger.info("Successfully connected to Qdrant")

            # Create collection if it doesn't exist
            self._create_collection_if_not_exists()
            logger.info("VectorDBService initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize VectorDBService: {e}")
            raise

    @retry(
        stop=stop_after_attempt(5),  # Increased retries
        wait=wait_exponential(multiplier=1, min=2, max=20),  # Adjusted wait times
        retry=retry_if_exception_type((Exception)),
    )
    def _create_collection_if_not_exists(self):
        """Create the collection if missing and ensure payload indexes."""
        try:
            # Prepare collection configuration
            distance_map = {
                "COSINE": models.Distance.COSINE,
                "DOT": models.Distance.DOT,
                "EUCLID": models.Distance.EUCLID,
            }
            distance = distance_map.get(self.settings.distance_metric)
            if not distance:
                raise ValueError(
                    f"Invalid distance metric: {self.settings.distance_metric}. "
                    f"Must be one of: {list(distance_map.keys())}"
                )

            vector_config = models.VectorParams(
                size=self.settings.vector_size,
                distance=distance,
            )

            try:
                # First attempt to get collection info
                collection_info = self.client.get_collection(self.collection_name)
                logger.info(f"Collection '{self.collection_name}' exists with config: {collection_info}")
            except Exception as e:
                # Collection doesn't exist or other error, attempt to create
                logger.info(f"Creating collection '{self.collection_name}'...")
                
                # Force recreate the collection
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=vector_config,
                    force=True  # This ensures clean recreation if partially exists
                )
                logger.info(f"Successfully created collection '{self.collection_name}'")
            
            # Verify collection was created
            collection_info = self.client.get_collection(self.collection_name)
            if not collection_info:
                raise Exception(f"Failed to verify collection '{self.collection_name}' after creation")
            
            # Create indices
            self._create_required_indices()
            logger.info(f"Collection '{self.collection_name}' is ready for use")
            return True
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.settings.vector_size,
                    distance=distance,
                ),
            )
            logger.info(f"Collection '{self.collection_name}' created successfully.")
            self._create_required_indices()
            
        except Exception as e:
            logger.error(f"Failed to create/verify collection: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _create_required_indices(self):
        """
        Create payload indexes for hot filter keys (flattened).
        Add or remove as needed for your queries.
        """
        try:
            # Ensure collection exists before creating indices
            collection_info = self.client.get_collection(self.collection_name)
            if not collection_info:
                raise Exception(f"Collection '{self.collection_name}' not found")

            to_index = [
                ("source", models.PayloadSchemaType.KEYWORD),  # Changed from file_path to source
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
                        wait=True  # Wait for index creation to complete
                    )
                    logger.info(f"Created/verified index on '{field_name}'")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.debug(f"Index '{field_name}' already exists")
                    else:
                        logger.warning(f"Failed to create index '{field_name}': {e}")
                        raise
        except Exception as e:
            logger.error(f"Failed to create indices: {e}")
            raise

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

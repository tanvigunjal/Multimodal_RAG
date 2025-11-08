# src/ingestion/orchestrator.py

import asyncio
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.services.embedding_service import embedding_service
from src.services.vectordb_service import vectordb_service
from src.services.llm_service import llm_service
from src.ingestion.extractor import PDFExtractor
from src.ingestion.enricher import ContentEnricher
from src.ingestion.chunker import DocumentChunker
from src.ingestion.vector_manager import VectorStoreManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AgenticIngestionOrchestrator:
    """
    Orchestrates the entire document ingestion pipeline by managing a
    sequence of specialized tools.
    """
    def __init__(self, file_path: str, image_output_dir: str):
        self.file_path = file_path
        self.image_output_dir = image_output_dir

        # Initialize all the tools the agent will use
        settings = get_settings()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.ingestion.chunk_size,
            chunk_overlap=settings.ingestion.chunk_overlap,
        )
        
        self.extractor = PDFExtractor(file_path, image_output_dir)
        self.enricher = ContentEnricher(llm_service)
        self.chunker = DocumentChunker(file_path, text_splitter)
        self.vector_manager = VectorStoreManager(embedding_service, vectordb_service)

    async def run(self, progress_callback=None) -> bool:
        """Executes the agentic ingestion workflow.
        
        Args:
            progress_callback: Optional callback function(step: str, progress: int) to report progress
        
        Returns:
            bool: True if the document was processed, False if it was already in the database
        """
        
        def update_progress(step: str, progress: int):
            if progress_callback:
                progress_callback(step, progress)
            logger.info(f"Progress: {progress}% - {step}")
        
        # Check for duplicates first
        logger.info(f"Checking if document exists: {self.file_path}")
        update_progress("Checking for duplicates", 10)
        
        if self.vector_manager.is_document_processed(self.file_path):
            logger.warning(f"Document '{self.file_path}' has already been processed. Skipping.")
            update_progress("Document already exists in database", 100)
            return False

        logger.info(f"Agent starting ingestion for: {self.file_path}")
        update_progress("Document is new, starting processing", 15)

        # === Step 1: EXTRACT (Use the extraction tool) ===
        update_progress("Extracting document content", 20)
        raw_elements = self.extractor.extract()
        if not raw_elements:
            logger.error("Extraction failed, no elements found. Aborting pipeline.")
            return False
        update_progress("Content extraction complete", 40)

        # === Step 2: ENRICH (Use the enrichment tool concurrently) ===
        update_progress("Enriching document content", 50)
        enriched_data = await self.enricher.enrich_elements(raw_elements)
        update_progress("Content enrichment complete", 70)

        # === Step 3: CHUNK (Use the chunking tool) ===
        update_progress("Chunking document content", 75)
        document_chunks = self.chunker.create_chunks(raw_elements, enriched_data)
        if not document_chunks:
            logger.error("Chunking produced no output. Aborting pipeline.")
            return False
        update_progress("Content chunking complete", 85)

        # === Step 4: LOAD (Use the vector store tool) ===
        update_progress("Loading chunks into vector database", 90)
        self.vector_manager.add_chunks(document_chunks)

        update_progress("Document processing complete", 100)
        logger.info(f"Agent successfully completed ingestion for: {self.file_path}")


async def main():
    """Main function to run the pipeline for a sample document."""
    PDF_FILE_PATH = "/Users/tanvigunjal/Desktop/Multimodal_RAG/data/Dummy.pdf"
    IMAGE_OUTPUT_DIR = "figures"

    try:
        orchestrator = AgenticIngestionOrchestrator(PDF_FILE_PATH, IMAGE_OUTPUT_DIR)
        await orchestrator.run()
        print("✅ Ingestion pipeline completed successfully.")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred during the ingestion pipeline: {e}")


if __name__ == "__main__":
    asyncio.run(main())
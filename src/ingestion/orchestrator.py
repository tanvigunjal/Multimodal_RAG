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

    async def run(self):
        """Executes the agentic ingestion workflow."""
        
        # Agentic decision: Should I process this file?
        if self.vector_manager.is_document_processed(self.file_path):
            logger.warning(f"Document '{self.file_path}' has already been processed. Skipping.")
            return

        logger.info(f"Agent starting ingestion for: {self.file_path}")

        # === Step 1: EXTRACT (Use the extraction tool) ===
        raw_elements = self.extractor.extract()
        if not raw_elements:
            logger.error("Extraction failed, no elements found. Aborting pipeline.")
            return

        # === Step 2: ENRICH (Use the enrichment tool concurrently) ===
        enriched_data = await self.enricher.enrich_elements(raw_elements)

        # === Step 3: CHUNK (Use the chunking tool) ===
        document_chunks = self.chunker.create_chunks(raw_elements, enriched_data)
        if not document_chunks:
            logger.error("Chunking produced no output. Aborting pipeline.")
            return

        # === Step 4: LOAD (Use the vector store tool) ===
        self.vector_manager.add_chunks(document_chunks)

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
# src/ingestion/enricher.py

import asyncio
from typing import List, Dict, Any, Tuple
from unstructured.documents.elements import Table, Image
from src.services.llm_service import LLMService, llm_service
from src.ingestion.prompt import get_table_summary_prompt, get_image_caption_prompt
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ContentEnricher:
    """
    A tool for enriching extracted document elements using LLM calls.
    It processes all enrichment tasks concurrently for maximum speed.
    """

    def __init__(self, llm_service_instance: LLMService):
        self.llm_service = llm_service_instance

    async def _enrich_table(self, element: Table) -> Tuple[str, str]:
        """Asynchronously generates a summary for a single table."""
        table_html = getattr(element.metadata, "text_as_html", "")
        if not table_html:
            return element.id, "N/A"
        try:
            prompt = get_table_summary_prompt(table_html)
            summary = await asyncio.to_thread(self.llm_service.generate_text, prompt)
            return element.id, summary
        except Exception as e:
            logger.error(f"Failed to summarize table {element.id}: {e}", exc_info=True)
            return element.id, "Failed to generate summary."

    async def _enrich_image(self, element: Image) -> Tuple[str, str]:
        """Asynchronously generates a caption for a single image."""
        image_path = getattr(element.metadata, "image_path", "")
        if not image_path:
            return element.id, "N/A"
        try:
            prompt = get_image_caption_prompt()
            caption = await asyncio.to_thread(self.llm_service.generate_image_caption, image_path, prompt)
            return element.id, caption
        except Exception as e:
            logger.error(f"Failed to caption image {image_path}: {e}", exc_info=True)
            return element.id, "Failed to generate caption."

    async def enrich_elements(self, elements: List[Any]) -> Dict[str, str]:
        """
        Orchestrates the concurrent enrichment of all table and image elements.

        Args:
            elements: A list of raw elements from the PDFExtractor.

        Returns:
            A dictionary mapping element ID to its summary or caption.
        """
        tasks = []
        for element in elements:
            if isinstance(element, Table):
                tasks.append(self._enrich_table(element))
            elif isinstance(element, Image):
                tasks.append(self._enrich_image(element))
        
        if not tasks:
            return {}
            
        logger.info(f"Starting enrichment for {len(tasks)} tables and images...")
        results = await asyncio.gather(*tasks)
        logger.info("Enrichment complete.")
        
        return {element_id: content for element_id, content in results}
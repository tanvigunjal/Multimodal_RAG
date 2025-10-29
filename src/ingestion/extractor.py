# src/ingestion/extractor.py

import os
from typing import List, Any, Optional
from unstructured.partition.pdf import partition_pdf
from src.utils.logger import get_logger

logger = get_logger(__name__)

class PDFExtractor:
    """
    A tool dedicated to partitioning PDFs and extracting raw elements.
    It does not perform any data enrichment (e.g., LLM calls).
    """

    def __init__(self, doc_path: str, image_output_dir: str):
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"The specified file does not exist: {doc_path}")

        self.doc_path = doc_path
        # Ensure the final image directory exists.
        os.makedirs(image_output_dir, exist_ok=True)
        self.image_output_dir = image_output_dir

    def extract(self) -> List[Any]:
        """
        Partitions the PDF to extract text, tables, and images.

        Returns:
            A list of raw 'unstructured' elements. Returns an empty list on failure.
        """
        logger.info(f"Starting PDF partitioning for: {self.doc_path}")
        try:
            elements = partition_pdf(
                filename=self.doc_path,
                strategy="hi_res",
                extract_images_in_pdf=True,
                infer_table_structure=True,
                image_output_dir_path=self.image_output_dir,
            )
            logger.info(f"Successfully extracted {len(elements)} elements from {self.doc_path}")
            return elements
        except Exception as e:
            logger.error(f"Error partitioning {self.doc_path}: {e}", exc_info=True)
            return []
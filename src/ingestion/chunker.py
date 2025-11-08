# src/ingestion/chunker.py

import os
from typing import List, Dict, Any
from unstructured.documents.elements import Table, Image, Text, Title
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DocumentChunker:
    """
    A tool for creating structured document chunks from raw elements and
    pre-enriched content (summaries and captions).
    """

    def __init__(
        self,
        doc_path: str,
        text_splitter: RecursiveCharacterTextSplitter,
    ):
        self.doc_path = doc_path
        self.doc_name = os.path.basename(doc_path)
        self.doc_id = os.path.splitext(self.doc_name)[0]
        self.text_splitter = text_splitter

    def create_chunks(self, elements: List[Any], enriched_data: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Combines elements and their enrichments into final, structured chunks.
        """
        chunks: List[Dict[str, Any]] = []
        text_buffer: List[str] = []
        current_section = "Introduction"
        chunk_index = 0

        text_buffer = []
        current_page = None

        for i, element in enumerate(elements):
            is_last = i == len(elements) - 1
            element_page = getattr(element.metadata, "page_number", None)

            if isinstance(element, Title):
                current_section = element.text

            if isinstance(element, (Text, Title)):
                # Keep track of the text and its page number
                text_buffer.append({
                    "text": element.text,
                    "page": element_page or current_page
                })
                current_page = element_page or current_page

            # Flush buffer for non-text elements or at the end of the document
            if (not isinstance(element, (Text, Title))) or is_last:
                if text_buffer:
                    # Group text by page number
                    page_groups = {}
                    for item in text_buffer:
                        page = item["page"]
                        if page not in page_groups:
                            page_groups[page] = []
                        page_groups[page].append(item["text"])
                    
                    # Process each page group separately
                    for page, texts in page_groups.items():
                        full_text = "\n\n".join(texts)
                        for text_chunk in self.text_splitter.split_text(full_text):
                            meta = self._create_metadata(element, chunk_index, "text", current_section)
                            meta["structural_metadata"]["page_number"] = page
                            meta["raw_content"] = text_chunk
                            chunks.append(meta)
                            chunk_index += 1
                    text_buffer = []

            # Handle non-text elements using pre-enriched data
            if isinstance(element, Image):
                summary = enriched_data.get(element.id, "N/A")
                meta = self._create_metadata(element, chunk_index, "image", current_section, summary)
                meta["multimodal_metadata"]["image_path"] = getattr(element.metadata, "image_path", None)
                chunks.append(meta)
                chunk_index += 1
            elif isinstance(element, Table):
                summary = enriched_data.get(element.id, "N/A")
                meta = self._create_metadata(element, chunk_index, "table", current_section, summary)
                meta["multimodal_metadata"]["table_html"] = getattr(element.metadata, "text_as_html", None)
                chunks.append(meta)
                chunk_index += 1
        
        logger.info(f"Successfully created {len(chunks)} chunks for document: {self.doc_name}")
        return chunks

    def _create_metadata(self, element: Any, index: int, el_type: str, section: str, summary: str = "") -> Dict[str, Any]:
        page = getattr(element.metadata, "page_number", None)
        chunk_id = f"{self.doc_id}_p{page}_c{index}" if page is not None else f"{self.doc_id}_c{index}"
        
        return {
            "chunk_id": chunk_id,
            "document_metadata": {"file_path": self.doc_path, "file_name": self.doc_name}, 
            "structural_metadata": {"page_number": page, "section_heading": section, "element_type": el_type},
            "multimodal_metadata": {
                "figure_id": f"{el_type.capitalize()}_{page}_{index}" if page else f"{el_type.capitalize()}_{index}",
                "summary": summary,
                "modality": el_type,
            },
            "raw_content": summary, # Summary is the content for multimodal elements
        }
    

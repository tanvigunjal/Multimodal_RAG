# src/core/tools.py

import re
import difflib
import string
from typing import List, Optional, Dict
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_cohere import CohereRerank
from qdrant_client.http.models import FieldCondition, MatchValue, Filter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from src.config import get_settings
from src.core.retriever import build_vectorstore
from src.utils.logger import get_logger
from src.core.prompt import TITLE_GENERATOR_PROMPT

logger = get_logger(__name__)

class QueryAnalyzer:
    """Analyzes the user query to detect content preferences."""
    def analyze(self, query: str) -> Optional[str]:
        """Detects if the query hints at a specific content type."""
        q_lower = query.lower()
        if "image" in q_lower or "figure" in q_lower or "photo" in q_lower or "graph" in q_lower or "chart" in q_lower:
            return "image"
        if "table" in q_lower or "grid" in q_lower or "data" in q_lower:
            return "table"
        return None

class VectorRetriever:
    """A tool for retrieving documents from the vector store."""
    def __init__(self, vectorstore: QdrantVectorStore):
        self.vectorstore = vectorstore
        self.settings = get_settings().retriever

    def retrieve(self, query: str, content_type: Optional[str] = None) -> List[Document]:
        """Retrieves documents, with an optional filter for content type."""
        search_kwargs = {"k": self.settings.top_k}
        if content_type:
            logger.info(f"Filtering retrieval for element_type='{content_type}'")
            # --- CORRECTION APPLIED HERE ---
            # 1. Create the FieldCondition
            field_condition = FieldCondition(
                key="element_type",
                match=MatchValue(value=content_type),
            )
            # 2. Wrap the FieldCondition in a Filter object's 'must' clause
            # The Qdrant client expects this structure for a proper Filter.
            qdrant_filter = Filter(must=[field_condition])
            
            # 3. Pass the correctly formatted Qdrant Filter object to LangChain
            search_kwargs["filter"] = qdrant_filter # This object should be correctly validated/serialized
            
        retriever = self.vectorstore.as_retriever(search_kwargs=search_kwargs)
        return retriever.invoke({"input": query})

class Reranker:
    """A tool for reranking documents for relevance using Cohere."""
    def __init__(self):
        settings = get_settings().reranker
        self.compressor = CohereRerank(
            cohere_api_key=settings.cohere_api_key,
            model=settings.model,
            top_n=settings.top_k,
        )

    def rerank(self, documents: List[Document], query: str) -> List[Document]:
        """Compresses and reranks a list of documents against a query."""
        if not documents:
            return []
        return self.compressor.compress_documents(documents=documents, query=query)

class ContextFormatter:
    """Formats documents into a structured string for the LLM prompt."""
    def format_docs(self, docs: List[Document]) -> str:
        lines = []
        for d in docs:
            md = d.metadata or {}
            # Accessing the flattened metadata keys from the new ingestion pipeline.
            lines.append(
                "\n".join([
                    f"file_name: {md.get('file_name', '')}",
                    f"page_number: {md.get('page_number', '')}",
                    f"section_heading: {md.get('section_heading', '')}",
                    f"text: {d.page_content}",
                    f"image_path: {md.get('image_path', '')}",
                    f"summary: {md.get('summary', '')}",
                    "----",
                ])
            )
        return "\n".join(lines) if lines else "(no context)"

class OutputValidator:
    """Validates and normalizes LLM output, especially for image tags."""
    IMAGE_TAG_RE = re.compile(r"\[IMAGE:([^\]]+)\]")

    def _get_allowed_paths(self, docs: List[Document]) -> List[str]:
        """Extracts all valid image paths from the source documents."""
        paths = [
            str(d.metadata.get("image_path", "")).strip()
            for d in docs if d.metadata.get("image_path")
        ]
        return sorted(set(paths))

    def normalize(self, answer: str, source_docs: List[Document]) -> str:
        """
        Validates [IMAGE:...] placeholders against source documents.
        If a path is invalid, it is strictly removed.
        """
        allowed_paths = self._get_allowed_paths(source_docs)
        if not allowed_paths:
            # If there are no valid images, remove all image tags
            return self.IMAGE_TAG_RE.sub("", answer)

        def repl(match):
            raw_path = match.group(1).strip()
            # Strict check: path must be in the allowed list
            if raw_path in allowed_paths:
                return f"[IMAGE:{raw_path}]"
            
            # If not found, log it and remove the tag completely
            logger.warning(f"Removing invalid image path '{raw_path}' from response because it was not found in source documents.")
            return ""

        return self.IMAGE_TAG_RE.sub(repl, answer)

class TitleGenerator:
    """A tool for generating a three-word title for a user query."""
    def __init__(self):
        settings = get_settings()
        self.llm = ChatGoogleGenerativeAI(
            model=settings.llm.model_name,
            temperature=0,
            max_output_tokens=512,
            api_key=settings.llm.api_key,
        )

    async def generate(self, query: str) -> str:
        """Generates a three-word title for the given query."""
        
        try:
            # Now try with the chain
            chain = TITLE_GENERATOR_PROMPT | self.llm | StrOutputParser()
            cleaned_query = query.translate(str.maketrans('', '', string.punctuation))

            raw_title = await chain.ainvoke({"query": cleaned_query})

            # Robustly  clean the string of whitespace, quotes, and newlines
            title = raw_title.strip().strip('"').strip("'").strip()
            
            # --- FALLBACK LOGIC (Keep this) ---
            if not title:
                logger.warning(f"TitleGenerator (ChatPrompt) produced an empty title for query: '{query}'. Using a default.")
                # Create a default title from the first 3 words
                title = " ".join(query.split()[:3])
                if len(query.split()) > 3:
                    title += "..."
            
            logger.info(f"Final generated title: '{title}'") # Back to info
            
            return title

        except Exception as e:
            # This will catch API key errors or other network failures
            logger.error(f"Error during title chain.ainvoke: {e}", exc_info=True)
            # Provide a fallback title on error
            return " ".join(query.split()[:3]) + " (Error)"
# src/core/agent.py

from typing import Iterable, List, Optional
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.prompt import TEXT_QA_PROMPT
from src.core.tools import (
    QueryAnalyzer, VectorRetriever, Reranker, ContextFormatter, OutputValidator
)
from src.core.retriever import build_vectorstore
from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

import re
from typing import Iterable, List, Optional

class StreamingRAGResponse:
    """Container for a streaming response and its source documents."""
    def __init__(self, stream_iterator: Iterable[str], docs: List[Document]):
        self.response_gen = stream_iterator
        self.source_nodes = docs
        self._final_response: Optional[str] = None

    def get_response(self) -> dict:
        """
        Consumes the stream, cleans the final response by removing inline source citations,
        and returns the cleaned response and source documents.
        """
        if self._final_response is None:
            full_response = "".join(list(self.response_gen))
            
            # Post-process to remove inline citations
            answer_part = full_response
            sources_part = ""
            
            # Case-insensitive split by "Sources" at the beginning of a line.
            parts = re.split(r'(\n\s*Sources\b)', full_response, maxsplit=1, flags=re.IGNORECASE)
            
            answer_part = parts[0]
            if len(parts) > 1:
                sources_part = (parts[1] + parts[2]) if len(parts) > 2 else parts[1]

            # Regex to find and remove inline citations from the answer_part
            # Added a new rule: \bSources?:[^\n]*
            # This finds "Sources:" or "Source:" and removes the rest of that line.
            citation_pattern = re.compile(
                r'\s*('                         # Match optional whitespace and start capturing group
                r'\[.*?source.*?\]|'            # [Source: ...]
                r'\(.*?source.*?\)|'            # (Source: ...)
                r'\[\d+\]|'                      # [1]
                r'\(see.*?\)|'                   # (see doc)
                r'\(sources\)|'                  # (Sources) - literal string
                r'\([^)]*p\.\s*\d+[^)]*\)|'       # (p. 2) or (file, p. 2)
                r'\([^)]*page\s*\d+[^)]*\)|'      # (page 2) or (file, page 2)
                r'\([^)]*\.(pdf|docx?|pptx?)[^)]*\)|' # (file.pdf) or (file.pdf, etc.)
                r'\bSources?:[^\n]*'            # NEW RULE: Matches "Sources: ..." or "Source: ..." to the end of its line
                r')',
                re.IGNORECASE
            )
            
            cleaned_answer = citation_pattern.sub('', answer_part).strip()
           
            if sources_part:
                # Ensure there's clean separation
                self._final_response = f"{cleaned_answer}\n\n{sources_part.strip()}"
            else:
                self._final_response = cleaned_answer
        
        return {
            "response": self._final_response,
            "source_nodes": self.source_nodes,
        }

class RetrievalAgent:
    """
    An agent that orchestrates retrieval, reranking, and generation.
    """
    def __init__(self):
        settings = get_settings()
        
        # Initialize the agent's toolbox
        self.query_analyzer = QueryAnalyzer()
        self.vector_retriever = VectorRetriever(build_vectorstore())
        self.reranker = Reranker()
        self.formatter = ContextFormatter()
        self.validator = OutputValidator()

        # Initialize the LLM for generation
        self.llm = ChatGoogleGenerativeAI(
            model=settings.llm.model_name,
            temperature=settings.llm.temperature,
            max_output_tokens=settings.llm.max_tokens,
            convert_system_message_to_human=True,
            streaming=True,
            timeout=settings.llm.timeout,
            api_key=settings.llm.api_key,
        )
        logger.info("RetrievalAgent initialized with its toolbox.")

    def run(self, query: str) -> StreamingRAGResponse:
        """
        Executes the agent's plan to process a query and return a streaming response.
        """
        # === AGENTIC WORKFLOW ===

        # Step 1: Analyze the query for preferences
        logger.info(f"Agent received query: '{query}'")
        content_preference = self.query_analyzer.analyze(query)

        # Step 2: Hybrid Retrieval
        # Always perform a general search
        candidate_docs = self.vector_retriever.retrieve(query)
        
        # If a preference exists, perform a second, filtered search to boost it
        if content_preference:
            logger.info(f"Boosting search for type: '{content_preference}'")
            filtered_docs = self.vector_retriever.retrieve(query, content_type=content_preference)
            candidate_docs.extend(filtered_docs)
            
        # De-duplicate candidates before reranking
        unique_docs = list({doc.page_content: doc for doc in candidate_docs}.values())
        logger.info(f"Retrieved {len(unique_docs)} unique candidates.")

        # Step 3: Rerank for relevance
        final_docs = self.reranker.rerank(unique_docs, query)
        logger.info(f"Reranked to top {len(final_docs)} documents.")

        # Step 4: Format context for the LLM
        context_str = self.formatter.format_docs(final_docs)
        
        # Step 5: Generate the response
        prompt = TEXT_QA_PROMPT.partial(max_words="250")
        
        chain = (
            prompt
            | self.llm
            | StrOutputParser()
            # Step 6: Validate and normalize the output stream
            | RunnableLambda(lambda text: self.validator.normalize(text, final_docs))
        )
        
        stream_iterator = chain.stream({"context": context_str, "query": query})
        
        return StreamingRAGResponse(stream_iterator, final_docs)

# Singleton instance of the agent
retrieval_agent = RetrievalAgent()
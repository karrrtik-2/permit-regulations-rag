"""
RAG pipeline for state provision document processing.

Uses vector stores (FAISS/ChromaDB) with OpenAI embeddings
and custom LLM to extract structured information from
state provision PDFs.
"""

import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

import requests
from langchain.chains import ConversationalRetrievalChain
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_core.language_models import LLM
from openai import OpenAI
from PyPDF2 import PdfReader

from config.settings import settings
from db import get_db

logger = logging.getLogger(__name__)


class DeepInfraLLM(LLM):
    """Custom LangChain LLM wrapper for DeepInfra API.

    Uses the OpenAI-compatible DeepInfra endpoint with
    configurable model selection.
    """

    client: Optional[OpenAI] = None

    def __init__(self) -> None:
        super().__init__()
        api_key = settings.llm.deep_infra_key
        if not api_key:
            raise ValueError("DEEP_INFRA_KEY not configured")

        self.client = OpenAI(
            base_url=settings.llm.deep_infra_base_url,
            api_key=api_key,
        )

    @property
    def _llm_type(self) -> str:
        return "deep_infra_llama"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from the DeepInfra LLM.

        Args:
            prompt: The input prompt.
            stop: Optional stop sequences.

        Returns:
            Generated response text.
        """
        refined_prompt = (
            "Answer the following query in detail and to the point "
            "without prefacing with phrases like 'Based on the context' "
            f"or 'Here's what I found.' Provide only the answer:\n\n{prompt}"
        )

        messages = [{"role": "user", "content": refined_prompt}]

        try:
            stream = self.client.chat.completions.create(
                model=settings.llm.deep_infra_model,
                messages=messages,
                temperature=0.7,
                top_p=1,
                max_tokens=10000,
                stream=True,
            )

            response = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content is not None:
                    response += content
            return response

        except Exception as e:
            logger.error("DeepInfra LLM error: %s", e)
            return ""


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text content.
    """
    text = ""
    reader = PdfReader(pdf_path)

    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    return text


def create_text_chunks(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[str]:
    """Split text into overlapping chunks for embedding.

    Args:
        text: Input text to split.
        chunk_size: Size of each chunk. Defaults to config.
        chunk_overlap: Overlap between chunks. Defaults to config.

    Returns:
        List of text chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.rag.chunk_size,
        chunk_overlap=chunk_overlap or settings.rag.chunk_overlap,
        length_function=len,
    )
    return splitter.split_text(text)


def create_vectorstore(text_chunks: List[str]) -> FAISS:
    """Create a FAISS vector store from text chunks.

    Args:
        text_chunks: List of text strings to embed.

    Returns:
        FAISS vector store instance.
    """
    embeddings = OpenAIEmbeddings(
        model=settings.llm.embedding_model,
        openai_api_key=settings.llm.openai_api_key,
    )
    return FAISS.from_texts(texts=text_chunks, embedding=embeddings)


def create_qa_chain(vectorstore: FAISS) -> ConversationalRetrievalChain:
    """Create a conversational QA chain with the vector store.

    Args:
        vectorstore: FAISS vector store for retrieval.

    Returns:
        Configured ConversationalRetrievalChain.
    """
    return ConversationalRetrievalChain.from_llm(
        llm=DeepInfraLLM(),
        retriever=vectorstore.as_retriever(),
    )


def fetch_provision_pdf(state_name: str) -> str:
    """Download a state's provision PDF from MongoDB-stored URL.

    Args:
        state_name: Name of the state.

    Returns:
        Path to the downloaded temporary PDF file.

    Raises:
        ValueError: If no PDF link found for the state.
        Exception: If download fails.
    """
    db = get_db()
    doc = db.states.find_one({"state_name": state_name})

    if not doc or "info" not in doc or "provision" not in doc["info"]:
        raise ValueError(f"No provision PDF link found for state: {state_name}")

    pdf_url = doc["info"]["provision"]
    response = requests.get(pdf_url, stream=True, timeout=60)

    if response.status_code != 200:
        raise Exception(f"Failed to download PDF: {pdf_url}")

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    with open(temp.name, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            f.write(chunk)

    return temp.name


def _clean_response(text: str) -> str:
    """Clean up RAG response text."""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def process_state_provisions(
    state_name: str,
    topics: Optional[tuple] = None,
    output_path: Optional[str] = None,
) -> Dict[str, str]:
    """Process a state's provision PDF and extract topic-based information.

    Downloads the provision PDF, creates a QA chain, and queries
    each topic to build structured provision data.

    Args:
        state_name: Name of the state to process.
        topics: Tuple of topics to query. Defaults to config.
        output_path: Optional JSON output path.

    Returns:
        Dictionary mapping topics to extracted information.
    """
    topics = topics or settings.rag.provision_topics

    logger.info("Processing provisions for %s", state_name)
    pdf_path = fetch_provision_pdf(state_name)

    try:
        raw_text = extract_pdf_text(pdf_path)
        chunks = create_text_chunks(raw_text)
        vectorstore = create_vectorstore(chunks)
        qa_chain = create_qa_chain(vectorstore)

        results: Dict[str, str] = {}
        for topic in topics:
            query = f"Tell me everything about {topic}"
            response = qa_chain({"question": query, "chat_history": []})
            results[topic] = _clean_response(response["answer"])
            logger.info("Processed topic: %s", topic)

        # Save to file if requested
        if output_path:
            with open(output_path, "w") as f:
                json.dump(results, f, indent=4)

        # Update MongoDB
        db = get_db()
        db.states.update_one(
            {"state_name": state_name},
            {"$set": {"info.provision_info": results}},
        )

        logger.info("Successfully processed %s", state_name)
        return results

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

"""
ScreenRAG — RAG Engine (ChromaDB + SentenceTransformers)

Core Retrieval-Augmented Generation component with two responsibilities:

Part 1 — Knowledge Base Ingestion:
    Loads PDF textbooks → chunks text → generates embeddings → stores in ChromaDB
    Collections are role-scoped: ai_ml_kb, backend_kb, data_science_kb

Part 2 — Context Retrieval:
    Embeds a query → searches the role-specific collection → returns top-n chunks

Chunking strategy: sliding window (800 tokens, 150 overlap, sentence boundaries)
Embedding model: sentence-transformers all-MiniLM-L6-v2

Usage:
    # Ingestion (one-time, via knowledge_base/ingest.py)
    ingest_documents(["path/to/book.pdf"], "ai_ml_kb")

    # Retrieval (per question generation)
    chunks = retrieve_context("gradient descent optimization", "ai_ml", n_results=5)
"""

import os
import re
import logging
from typing import Optional

import pdfplumber
import chromadb
from sentence_transformers import SentenceTransformer

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton model + client instances
# ---------------------------------------------------------------------------
_embedding_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None


def _get_embedding_model() -> SentenceTransformer:
    """Lazily load the sentence-transformer embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    return _embedding_model


def _get_chroma_client() -> chromadb.PersistentClient:
    """Lazily initialize the ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        logger.info(f"ChromaDB client initialized at {settings.CHROMA_PERSIST_DIR}")
    return _chroma_client


# ---------------------------------------------------------------------------
# Role → Collection mapping
# ---------------------------------------------------------------------------
ROLE_COLLECTION_MAP = {
    "ai_ml": "ai_ml_kb",
    "backend": "backend_kb",
    "data_science": "data_science_kb",
}


def _get_collection_name(role: str) -> str:
    """Map a role identifier to its ChromaDB collection name."""
    return ROLE_COLLECTION_MAP.get(role, f"{role}_kb")


# ---------------------------------------------------------------------------
# Text chunking — sliding window with sentence boundaries
# ---------------------------------------------------------------------------
def _split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex.
    Handles common abbreviations and decimal numbers.
    """
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    # Also split on newlines that look like paragraph breaks
    result = []
    for sent in sentences:
        sub_sents = re.split(r'\n{2,}', sent)
        result.extend(sub_sents)
    return [s.strip() for s in result if s.strip()]


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation (words ≈ 0.75 tokens for English)."""
    return int(len(text.split()) * 1.33)


def chunk_text(
    text: str,
    max_tokens: int = 800,
    overlap_tokens: int = 150,
) -> list[str]:
    """
    Split text into overlapping chunks at sentence boundaries.
    
    Strategy:
        - Accumulate sentences until the chunk reaches max_tokens
        - When full, save the chunk and start a new one from the overlap point
        - Never split mid-sentence
    
    Args:
        text: Input text to chunk.
        max_tokens: Maximum tokens per chunk (~800 tokens).
        overlap_tokens: Number of overlapping tokens between chunks (~150).
    
    Returns:
        List of text chunks.
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = _estimate_tokens(sentence)

        # If adding this sentence exceeds the limit, finalize current chunk
        if current_tokens + sent_tokens > max_tokens and current_sentences:
            chunk = " ".join(current_sentences)
            chunks.append(chunk)

            # Calculate overlap: keep sentences from the end that fit in overlap_tokens
            overlap_sentences: list[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = _estimate_tokens(s)
                if overlap_count + s_tokens > overlap_tokens:
                    break
                overlap_sentences.insert(0, s)
                overlap_count += s_tokens

            current_sentences = overlap_sentences
            current_tokens = overlap_count

        current_sentences.append(sentence)
        current_tokens += sent_tokens

    # Don't forget the last chunk
    if current_sentences:
        chunk = " ".join(current_sentences)
        chunks.append(chunk)

    return chunks


# ---------------------------------------------------------------------------
# Part 1 — Knowledge Base Ingestion
# ---------------------------------------------------------------------------
def ingest_documents(
    pdf_paths: list[str],
    collection_name: str,
    role: str = "",
) -> int:
    """
    Ingest PDF documents into a ChromaDB collection.
    
    Idempotent: skips if the collection already has documents.
    
    Pipeline:
        1. Check if collection already populated → skip if so
        2. Extract text page-by-page via pdfplumber
        3. Chunk text with sliding window (800 tokens, 150 overlap)
        4. Generate embeddings with SentenceTransformer
        5. Store in ChromaDB with metadata
    
    Args:
        pdf_paths: List of paths to PDF files.
        collection_name: ChromaDB collection name (e.g., "ai_ml_kb").
        role: Role identifier for metadata (e.g., "ai_ml").
    
    Returns:
        Total number of chunks ingested.
    """
    client = _get_chroma_client()
    model = _get_embedding_model()

    # Get or create collection
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Idempotent check: skip if already has documents
    existing_count = collection.count()
    if existing_count > 0:
        logger.info(
            f"Collection '{collection_name}' already has {existing_count} documents. "
            f"Skipping ingestion."
        )
        return existing_count

    total_chunks = 0
    all_documents: list[str] = []
    all_metadatas: list[dict] = []
    all_ids: list[str] = []

    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF file not found, skipping: {pdf_path}")
            continue

        filename = os.path.basename(pdf_path)
        logger.info(f"Ingesting {filename} → {collection_name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text()
                        if not text or not text.strip():
                            continue

                        # Chunk the page text
                        page_chunks = chunk_text(text)
                        
                        for chunk_idx, chunk in enumerate(page_chunks):
                            chunk_id = f"{collection_name}_{filename}_{page_num}_{chunk_idx}"
                            
                            all_documents.append(chunk)
                            all_metadatas.append({
                                "source_file": filename,
                                "page_number": page_num + 1,
                                "chunk_index": chunk_idx,
                                "role": role,
                            })
                            all_ids.append(chunk_id)
                            total_chunks += 1

                            if total_chunks % 50 == 0:
                                logger.info(
                                    f"  Ingesting {filename} → {collection_name} | "
                                    f"Chunk {total_chunks}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"  Failed to process page {page_num + 1} of {filename}: {e}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Failed to open PDF {filename}: {e}")
            continue

    if not all_documents:
        logger.warning(f"No documents to ingest into {collection_name}")
        return 0

    # Generate embeddings in batch
    logger.info(f"Generating embeddings for {len(all_documents)} chunks...")
    embeddings = model.encode(all_documents, show_progress_bar=True).tolist()

    # Add to ChromaDB in batches (ChromaDB has a per-call limit)
    batch_size = 500
    for i in range(0, len(all_documents), batch_size):
        end = min(i + batch_size, len(all_documents))
        collection.add(
            documents=all_documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=all_metadatas[i:end],
            ids=all_ids[i:end],
        )

    logger.info(
        f"Ingestion complete: {total_chunks} chunks → {collection_name}"
    )
    return total_chunks


# ---------------------------------------------------------------------------
# Part 2 — Context Retrieval
# ---------------------------------------------------------------------------
def retrieve_context(
    query: str,
    role: str,
    n_results: int = 5,
) -> list[str]:
    """
    Retrieve relevant document chunks for a query from the role-specific collection.
    
    Args:
        query: Search query (e.g., resume skills + topic).
        role: Role identifier ('ai_ml', 'backend', 'data_science').
        n_results: Number of top results to return.
    
    Returns:
        List of relevant text chunks, ordered by relevance.
        Returns empty list if the collection is empty or doesn't exist.
    """
    try:
        client = _get_chroma_client()
        model = _get_embedding_model()
        collection_name = _get_collection_name(role)

        # Check if collection exists and has documents
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            logger.info(f"Collection '{collection_name}' not found. Returning empty context.")
            return []

        if collection.count() == 0:
            logger.info(f"Collection '{collection_name}' is empty. Returning empty context.")
            return []

        # Embed the query
        query_embedding = model.encode([query]).tolist()

        # Query ChromaDB
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(n_results, collection.count()),
        )

        # Extract document texts
        documents = results.get("documents", [[]])[0]
        
        logger.info(
            f"Retrieved {len(documents)} chunks from '{collection_name}' "
            f"for query: {query[:80]}..."
        )
        return documents

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Utility — check ChromaDB health
# ---------------------------------------------------------------------------
def check_chroma_health() -> dict:
    """Check if ChromaDB is accessible and report collection stats."""
    try:
        client = _get_chroma_client()
        collections = client.list_collections()
        stats = {}
        for col in collections:
            stats[col.name] = col.count()
        return {
            "available": True,
            "collections": stats,
            "persist_dir": settings.CHROMA_PERSIST_DIR,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}

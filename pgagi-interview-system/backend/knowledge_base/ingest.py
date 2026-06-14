"""
ScreenRAG — Knowledge Base Ingestion Script

One-time script to load ML textbook PDFs into ChromaDB collections.
Each role gets its own collection with role-scoped documents.

Usage:
    cd backend
    python knowledge_base/ingest.py

    # Or from project root:
    python -m knowledge_base.ingest

Idempotent: re-running will NOT duplicate chunks (skips populated collections).
"""

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import sys
import logging

# Ensure backend directory is on the Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from services.rag_engine import ingest_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest")


# ---------------------------------------------------------------------------
# Role → PDF file mapping
# ---------------------------------------------------------------------------
# Place PDF textbooks in the `knowledge_base/pdfs/` directory
# The filenames here should match the actual PDF files you have

PDFS_DIR = os.path.join(SCRIPT_DIR, "pdfs")

ROLE_PDFS = {
    "ai_ml": [
        os.path.join(PDFS_DIR, "ml_absolute_beginners.pdf"),
        os.path.join(PDFS_DIR, "ai_ml_dl.pdf"),
    ],
    "data_science": [
        os.path.join(PDFS_DIR, "intro_ml_python.pdf"),
        os.path.join(PDFS_DIR, "ai_ml_dl.pdf"),
    ],
    "backend": [
        os.path.join(PDFS_DIR, "ml_absolute_beginners.pdf"),
    ],
}

# Collection name mapping (matches rag_engine.py)
ROLE_COLLECTION_MAP = {
    "ai_ml": "ai_ml_kb",
    "backend": "backend_kb",
    "data_science": "data_science_kb",
}


def main():
    """Main ingestion entry point."""
    logger.info("=" * 60)
    logger.info("ScreenRAG Knowledge Base Ingestion")
    logger.info("=" * 60)

    # Ensure PDFs directory exists
    os.makedirs(PDFS_DIR, exist_ok=True)

    total_ingested = 0
    roles_processed = 0

    for role, pdf_files in ROLE_PDFS.items():
        collection_name = ROLE_COLLECTION_MAP[role]
        
        logger.info(f"\n--- Processing role: {role} → collection: {collection_name} ---")

        # Check which PDFs actually exist
        existing_pdfs = [p for p in pdf_files if os.path.exists(p)]
        missing_pdfs = [p for p in pdf_files if not os.path.exists(p)]

        if missing_pdfs:
            for mp in missing_pdfs:
                logger.warning(f"  PDF not found (skipping): {os.path.basename(mp)}")

        if not existing_pdfs:
            logger.warning(
                f"  No PDF files found for role '{role}'. "
                f"Place PDFs in: {PDFS_DIR}"
            )
            continue

        logger.info(f"  Found {len(existing_pdfs)} PDF(s) to ingest:")
        for p in existing_pdfs:
            logger.info(f"    - {os.path.basename(p)}")

        # Ingest
        chunks = ingest_documents(
            pdf_paths=existing_pdfs,
            collection_name=collection_name,
            role=role,
        )

        total_ingested += chunks
        roles_processed += 1
        logger.info(f"  → {chunks} chunks in collection '{collection_name}'")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Ingestion complete: {total_ingested} total chunks across {roles_processed} roles")
    logger.info(f"{'=' * 60}")

    if total_ingested == 0:
        logger.warning(
            "\nNo documents were ingested. To populate the knowledge base:\n"
            f"  1. Place PDF textbook files in: {PDFS_DIR}\n"
            "  2. Expected filenames:\n"
            "     - ml_absolute_beginners.pdf\n"
            "     - intro_ml_python.pdf\n"
            "     - ai_ml_dl.pdf\n"
            "  3. Re-run this script: python knowledge_base/ingest.py\n"
        )


if __name__ == "__main__":
    main()

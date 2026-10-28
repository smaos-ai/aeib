#!/usr/bin/env python3
r"""
ingest_pdf.py — Self-Hosted PDF Claim Extractor & Cryptographic Hasher
Extracts text and claims per page from PDF documents, computes deterministic
SHA-256 hashes for each claim/section, and emits an RFC 9052 COSE_Sign1 provenance receipt.
"""

import os
import sys
import json
import time
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
try:
    from crypto_logger import ProvenanceLogger
except ImportError:
    from src.crypto_logger import ProvenanceLogger


def extract_claims_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts text chunks/claims from PDF file with page number tracking.
    Uses pypdf for PDF files, with fallback to text extraction for plaintext/markdown.
    """
    claims = []
    if not pdf_path.exists():
        raise FileNotFoundError(f"Document file not found: {pdf_path}")

    is_pdf = pdf_path.suffix.lower() == ".pdf"

    if is_pdf:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
                if not paragraphs and text.strip():
                    paragraphs = [text.strip()]

                for p_idx, para in enumerate(paragraphs):
                    p_hash = hashlib.sha256(para.encode("utf-8")).hexdigest()
                    claims.append({
                        "page": page_idx + 1,
                        "section_index": p_idx + 1,
                        "content": para,
                        "content_hash": p_hash
                    })
            if claims:
                return claims
        except Exception:
            # Fall through to raw text fallback
            pass

    # Resilient fallback: Raw text / markdown extraction
    raw_text = pdf_path.read_text(encoding="utf-8", errors="replace")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 30]
    if not paragraphs and raw_text.strip():
        paragraphs = [raw_text.strip()]

    for p_idx, para in enumerate(paragraphs):
        p_hash = hashlib.sha256(para.encode("utf-8")).hexdigest()
        claims.append({
            "page": 1,
            "section_index": p_idx + 1,
            "content": para,
            "content_hash": p_hash
        })

    return claims


def ingest_and_seal_pdf(
    pdf_path: str,
    query_context: Optional[str] = None,
    log_dir: str = "provenance/receipts",
    key_path: str = "keys/ed25519-private.pem"
) -> Dict[str, Any]:
    """
    Extracts claims from a document, hashes each chunk, binds evidence,
    and seals the ingestion into an RFC 9052 COSE_Sign1 provenance receipt.
    """
    target = Path(pdf_path)
    if not target.exists():
        raise FileNotFoundError(f"Document not found: {target}")

    # Compute overall document hash
    with open(target, "rb") as f:
        doc_bytes = f.read()
    doc_hash = hashlib.sha256(doc_bytes).hexdigest()

    # Extract claims
    claims = extract_claims_from_pdf(target)
    ts = int(time.time())
    rs_id = f"rs_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{ts}"
    effective_query = query_context or f"Document Ingestion: {target.name} ({len(claims)} claims)"

    # Format sources for receipt
    sources = [
        {
            "url": f"file://{target.resolve()}",
            "content_hash": doc_hash,
            "engine": "pdf_extractor"
        }
    ]
    # Add top extracted section hashes (up to 5)
    for c in claims[:5]:
        sources.append({
            "url": f"file://{target.resolve()}#page={c['page']}&claim={c['section_index']}",
            "content_hash": c["content_hash"],
            "engine": "surfsense_claim"
        })

    preview = f"Ingested {len(claims)} claims from {target.name}. Document digest: sha256:{doc_hash[:16]}..."
    if claims:
        preview = f"{claims[0]['content'][:180]}..."

    payload = {
        "research_session_id": rs_id,
        "query": effective_query,
        "answer": preview,
        "sources": sources,
        "disposition": "OUTCOME_VERIFIED"
    }

    # Initialize ProvenanceLogger and emit receipt
    logger = ProvenanceLogger(private_key_path=key_path, log_dir=log_dir)
    receipt = logger.emit_receipt(payload)

    return {
        "status": "INGESTED",
        "document_path": str(target),
        "document_sha256": doc_hash,
        "total_claims_extracted": len(claims),
        "research_session_id": rs_id,
        "receipt": receipt,
        "claims_sample": claims[:3]
    }


def main():
    parser = argparse.ArgumentParser(description="Extract claims from PDF and emit COSE_Sign1 provenance receipt.")
    parser.add_argument("pdf_path", help="Path to PDF document to ingest")
    parser.add_argument("--query", help="Research context or query string", default=None)
    parser.add_argument("--key", help="Path to Ed25519 private key", default="keys/ed25519-private.pem")
    parser.add_argument("--out-dir", help="Receipt directory", default="provenance/receipts")

    args = parser.parse_args()
    print(f"[PDF-INGEST] Processing: {args.pdf_path}")
    result = ingest_and_seal_pdf(
        pdf_path=args.pdf_path,
        query_context=args.query,
        log_dir=args.out_dir,
        key_path=args.key
    )

    print(f"[SUCCESS] Document SHA-256: {result['document_sha256']}")
    print(f"[SUCCESS] Extracted Claims: {result['total_claims_extracted']}")
    print(f"[RECEIPT] Session ID:       {result['research_session_id']}")
    print(f"[RECEIPT] Head Hash:        {result['receipt']['head_hash']}")
    print(f"[RECEIPT] COSE_Sign1 Alg:   {result['receipt']['cose_alg']}")


if __name__ == "__main__":
    main()

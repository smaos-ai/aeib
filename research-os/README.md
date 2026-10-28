# Research OS — Daily Edition Stack

A complete, self-hosted Perplexity + NotebookLM + Elicit replacement with cryptographic provenance:
- **Vane (Perplexica)**: Open-source Perplexity UI on port `3000`.
- **SearXNG**: Zero-cost, privacy-preserving metasearch engine on port `8080`.
- **SurfSense**: Academic memory, PDF ground-truth extraction, and citation synthesizer on port `3001`.
- **SMAOS Provenance Engine**: RFC 8785 JCS canonicalization, Ed25519 signing, and RFC 9052 COSE_Sign1 receipts.

### Starting the Stack
```bash
docker compose -f research-os/docker-compose.yml up -d
```

### Running a Provenance-Tracked Research Query
```bash
python3 scripts/research.py "Your query here"
```

### Ingesting Research PDFs
```bash
python3 scripts/ingest_pdf.py path/to/paper.pdf --query "Paper title / topic"
```

### Verifying Provenance Receipts
```bash
python3 scripts/verify.py provenance/receipts
```

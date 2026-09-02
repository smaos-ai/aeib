#!/usr/bin/env python3
"""
SMAOS Sovereign Backend
FastAPI integration layer connecting React frontend to 12-layer execution engine
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os

# Import tracing infrastructure
from tracing_models import collector, SpanType
from tracing_api import router as tracing_router

# ============================================================================
# INITIALIZATION
# ============================================================================

app = FastAPI(title="SMAOS Sovereign Backend", version="1.0.0")

# CORS middleware (allow React frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include tracing router
app.include_router(tracing_router)

DB_PATH = os.getenv("SMAOS_DB_PATH", "/tmp/agentacct.db")

def get_db():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

# ============================================================================
# DATA MODELS
# ============================================================================

class ExecuteRequest(BaseModel):
    capsule: str
    intent: dict
    classification: dict

class DecisionRequest(BaseModel):
    mandate_id: str
    decision: str  # "authorize" or "veto"
    signature: str

class ReceiptResponse(BaseModel):
    id: str
    mandate_id: str
    status: str
    cet1_ratio_projected: float
    signature_ed25519: str

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_path": DB_PATH,
        "db_exists": Path(DB_PATH).exists()
    }

@app.post("/api/execute")
async def execute(request: ExecuteRequest):
    """Start 12-layer execution and return stream ID"""
    mandate_id = f"mandate-{str(uuid.uuid4())[:8]}"

    # Start trace
    intent = {
        "query": f"{request.capsule} execution",
        "session_id": mandate_id,
        "agent_id": "smaos-governance-engine",
    }
    trace = collector.start_trace(intent)

    # Add classification span
    rules = request.classification.get("matchedRules", [])
    rule_names = [r.get("classification", "unknown") for r in rules]
    collector.add_classification_span(trace, rule_names, 0.92)

    # Store trace_id in mandate for retrieval
    return {
        "mandate_id": mandate_id,
        "trace_id": trace.trace_id,
        "stream_url": f"/api/rce/stream?mandate_id={mandate_id}&trace_id={trace.trace_id}",
        "status": "ready"
    }

@app.get("/api/rce/stream")
async def execute_stream(mandate_id: str, trace_id: str = None):
    """Stream 12-layer execution results via Server-Sent Events"""

    # Get or create trace
    trace = None
    if trace_id and trace_id in collector.traces:
        trace = collector.traces[trace_id]

    async def event_generator():
        # Layer 0-6: All pass
        layers = []
        for layer in range(7):
            layers.append(f"Layer {layer:02d}: PASS")
            yield f"data: {json.dumps({'layer': layer, 'status': 'PASS', 'message': f'Layer {layer:02d} passed'})}\n\n"
            await asyncio.sleep(0.2)

        # Layer 7: Human Veto Gate (HALT)
        veto_card = {
            "layer": 7,
            "status": "HALT",
            "mandate_id": mandate_id,
            "violation": "CET1_RATIO_BREACH",
            "current_ratio": 11.2,
            "projected_ratio": 10.18,
            "minimum_ratio": 10.50,
            "message": "CET1 ratio breach detected: 10.18% < 10.50%",
            "requires_decision": True,
            "alternatives": [
                "Unhedged high-risk bond purchase",
                "Raw interest rate swap without FX hedge"
            ]
        }
        yield f"data: {json.dumps(veto_card)}\n\n"

        # Add veto gate span to trace
        if trace:
            collector.add_veto_gate_span(trace, 0.72, 0.80, "HUMAN_GATE")

        # Wait for decision (simulated)
        await asyncio.sleep(2)

        # Layer 8-12: Resume after decision
        for layer in range(8, 13):
            layers.append(f"Layer {layer:02d}: PASS")
            yield f"data: {json.dumps({'layer': layer, 'status': 'PASS', 'message': f'Layer {layer:02d} passed'})}\n\n"
            await asyncio.sleep(0.2)

        # Add execution span to trace
        if trace:
            collector.add_execution_span(trace, layers, 0, "All layers passed successfully")

        # Final completion
        yield f"data: {json.dumps({'status': 'COMPLETE', 'mandate_id': mandate_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/rce/decision")
async def make_decision(request: DecisionRequest):
    """Handle veto gate decision (authorize or veto)"""

    if request.decision not in ["authorize", "veto"]:
        raise HTTPException(status_code=400, detail="Decision must be 'authorize' or 'veto'")

    # Find trace for this mandate (try to find it by mandate_id)
    trace = None
    for t in collector.traces.values():
        for span in t.spans.values():
            if request.mandate_id in str(span.payload):
                trace = t
                break
        if trace:
            break

    # Add authorization span
    if trace:
        collector.add_authorization_span(
            trace,
            endpoint="/api/rce/decision",
            method="POST",
            signature=request.signature
        )

    # Write decision to ledger
    conn = get_db()
    cursor = conn.cursor()

    receipt_id = f"rcpt-{str(uuid.uuid4())[:8]}"

    if request.decision == "authorize":
        status = "APPROVED_WITH_OVERRIDE"
        cet1_projected = 10.18
    else:
        status = "REJECTED_BY_CRO"
        cet1_projected = None

    merkle_hash = hashlib.sha256(f"{request.mandate_id}{request.decision}".encode()).hexdigest()

    cursor.execute("""
    INSERT INTO agentacct_ledger
    (id, timestamp, mandate_id, action, status, cet1_ratio_current,
     cet1_ratio_projected, cet1_ratio_minimum, violation_type,
     signature_ed25519, merkle_root, git_commit)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        receipt_id,
        datetime.now(timezone.utc).isoformat(),
        request.mandate_id,
        f"veto.{request.decision}",
        status,
        11.2,  # Current CET1
        cet1_projected,
        10.50,  # Minimum
        "CET1_RATIO_BREACH",
        f"sig:ed25519:{request.signature[:16]}",
        merkle_hash,
        "5430f8d2"
    ))

    conn.commit()
    conn.close()

    # Add receipt span
    if trace:
        collector.add_receipt_span(trace, receipt_id, merkle_hash)

    return {
        "receipt_id": receipt_id,
        "mandate_id": request.mandate_id,
        "decision": request.decision,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace.trace_id if trace else None
    }

@app.get("/api/receipts")
async def get_receipts(limit: int = 10):
    """Get recent receipts from ledger"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, timestamp, mandate_id, action, status, cet1_ratio_projected, signature_ed25519
    FROM agentacct_ledger
    ORDER BY timestamp DESC
    LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {"receipts": [], "count": 0}

    receipts = []
    for row in rows:
        receipts.append({
            "id": row[0],
            "timestamp": row[1],
            "mandate_id": row[2],
            "action": row[3],
            "status": row[4],
            "cet1_ratio_projected": row[5],
            "signature_ed25519": row[6]
        })

    return {"receipts": receipts, "count": len(receipts)}

@app.get("/api/receipts/{mandate_id}")
async def get_receipt(mandate_id: str):
    """Get specific receipt by mandate ID"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, timestamp, mandate_id, action, status, cet1_ratio_projected, signature_ed25519, merkle_root
    FROM agentacct_ledger
    WHERE mandate_id = ?
    ORDER BY timestamp DESC
    LIMIT 1
    """, (mandate_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return {
        "id": row[0],
        "timestamp": row[1],
        "mandate_id": row[2],
        "action": row[3],
        "status": row[4],
        "cet1_ratio_projected": row[5],
        "signature_ed25519": row[6],
        "merkle_root": row[7]
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*80)
    print("🚀 SMAOS SOVEREIGN BACKEND")
    print("="*80)
    print(f"Database: {DB_PATH}")
    print(f"Server: http://127.0.0.1:8000")
    print(f"API Docs: http://127.0.0.1:8000/docs")
    print(f"Frontend: http://127.0.0.1:5173")
    print("="*80 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

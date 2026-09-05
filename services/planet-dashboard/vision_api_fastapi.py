#!/usr/bin/env python3
"""
FastAPI Vision API — Governance Decision Support Layer
Integrates pure-Python HumanGate governance engine for fail-closed policy enforcement.
Routes:
  POST /v1/govern       — Submit governance request, get decision + Merkle proof
  GET  /health          — Health check
  GET  /metrics         — Audit trail + latency metrics
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional, List, Set
import uvicorn
import time
import json
from datetime import datetime, timezone
import asyncio

# Import pure-Python backend
from vision_api import (
    VisionAPI,
    GovernRequest as PythonGovernRequest,
    HumanGatePolicy,
    RiskLevel,
    HumanGateProof as PythonHumanGateProof,
)

# ═════════════════════════════════════════════════════════════
# 1. REQUEST/RESPONSE MODELS
# ═════════════════════════════════════════════════════════════


class GovernRequestModel(BaseModel):
    """HTTP request model for governance check"""
    request_id: str = Field(..., description="Unique request identifier")
    action: str = Field(..., description="Action being evaluated (e.g., 'read', 'delete')")
    blast_radius: float = Field(..., ge=0.0, le=1.0, description="Risk score (0.0-1.0)")
    user_id: str = Field(..., description="User identifier")
    app_id: str = Field(..., description="Application identifier")
    human_approved: bool = Field(default=False, description="Whether human approved")


class HumanGateProofModel(BaseModel):
    """Merkle proof + audit metadata"""
    merkle_root: str
    timestamp: str
    decision_id: str
    approved_by: Optional[str] = None
    auto_approved: bool


class GovernResponseModel(BaseModel):
    """HTTP response model for governance decision"""
    approved: bool
    charge_amount: int
    merkle_proof: Optional[HumanGateProofModel] = None
    error: Optional[str] = None
    reason: str
    request_id: str
    timestamp: str


class HealthModel(BaseModel):
    """Health check response"""
    status: str
    uptime_seconds: float
    requests_processed: int


# ═════════════════════════════════════════════════════════════
# 2. FASTAPI APPLICATION
# ═════════════════════════════════════════════════════════════

app = FastAPI(
    title="Vision API",
    description="Governance decision support layer with fail-closed gates",
    version="0.1.0"
)

# Global state
_vision_api = VisionAPI()
_start_time = time.time()
_requests_processed = 0


# ═════════════════════════════════════════════════════════════
# WebSocket Manager
# ═════════════════════════════════════════════════════════════

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


# ═════════════════════════════════════════════════════════════
# 3. ROUTES
# ═════════════════════════════════════════════════════════════

@app.post("/v1/govern", response_model=GovernResponseModel)
async def govern(request: GovernRequestModel) -> GovernResponseModel:
    """
    Governance decision endpoint (fail-closed).

    Flow:
    1. Accept GovernRequest with user input
    2. Call Vision API pre_execute_check()
    3. Return decision: approved (with charge) or denied (zero charge, error)

    Returns:
        GovernResponseModel with approved flag, charge_amount, and Merkle proof
    """
    global _requests_processed
    _requests_processed += 1

    try:
        # Convert HTTP request to Python GovernRequest
        govern_req = PythonGovernRequest(
            request_id=request.request_id,
            action=request.action,
            blast_radius=request.blast_radius,
            user_id=request.user_id,
            app_id=request.app_id,
            human_approved=request.human_approved,
        )

        # Call governance engine (fail-closed)
        result = _vision_api.pre_execute_check(govern_req)

        # Convert result to response
        proof_model = None
        if result.proof is not None:
            proof_model = HumanGateProofModel(
                merkle_root=result.proof.merkle_root,
                timestamp=result.proof.timestamp,
                decision_id=result.proof.decision_id,
                approved_by=result.proof.approved_by,
                auto_approved=result.proof.auto_approved,
            )

        response = GovernResponseModel(
            approved=result.allowed,
            charge_amount=result.charge_amount,
            merkle_proof=proof_model,
            error=result.error,
            reason=result.reason,
            request_id=request.request_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "governance_decision",
            "approved": result.allowed,
            "charge_amount": result.charge_amount,
            "reason": result.reason,
            "request_id": request.request_id,
            "merkle_root": proof_model.merkle_root if proof_model else None,
            "timestamp": response.timestamp,
        })

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/health", response_model=HealthModel)
async def health() -> HealthModel:
    """Health check endpoint"""
    uptime = time.time() - _start_time
    return HealthModel(
        status="healthy",
        uptime_seconds=uptime,
        requests_processed=_requests_processed,
    )


@app.get("/metrics")
async def metrics():
    """Return audit trail and performance metrics"""
    uptime = time.time() - _start_time
    return {
        "uptime_seconds": uptime,
        "requests_processed": _requests_processed,
        "avg_request_time_ms": (uptime / max(_requests_processed, 1)) * 1000,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time governance event streaming.

    Client connects: ws://localhost:8000/ws
    Server broadcasts governance decisions in real-time.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages (heartbeat)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)


# ═════════════════════════════════════════════════════════════
# 4. MAIN
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "vision_api_fastapi:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        reload=False,
    )

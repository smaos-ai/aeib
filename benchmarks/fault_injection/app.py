#!/usr/bin/env python3
r"""
app.py — Target Payment/Debit API with Fault Injection
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Exposes:
  - POST /debit: Commits debit to SQLite, then executes post-commit fault logic
  - GET /operations/{intent_id}: Authoritative out-of-band reconciliation
  - POST /admin/fault-config: Dynamically enables/configures fault injection
  - POST /admin/reset: Resets ledger and accounts for clean trial runs
"""

from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from benchmarks.fault_injection.store import AtomicDebitStore
from benchmarks.fault_injection.middleware import DeterministicFaultMiddleware, FaultConfig

# Initialize shared atomic store and fault config
store = AtomicDebitStore()
fault_config = FaultConfig(enabled=True, fault_mode="POST_COMMIT_504", post_commit_delay_ms=5.0)

app = FastAPI(
    title="AEIB Target Payment Ledger API",
    description="Hermetic target backend for demonstrating double-mutation under network drops and semantic drift",
    version="0.2.2",
)

# Attach fault injection middleware
app.add_middleware(DeterministicFaultMiddleware, config=fault_config)


class DebitRequest(BaseModel):
    logical_operation_id: str = Field(..., description="The unique logical business operation (e.g. op-inv-001)")
    intent_id: str = Field(..., description="Client-generated intent ID / request ID")
    account_id: str = Field(default="acc_primary", description="Account to debit")
    amount: float = Field(..., gt=0, description="Amount to debit")
    description: Optional[str] = Field(default="", description="Descriptive note (subject to semantic drift)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary client metadata")


class FaultConfigRequest(BaseModel):
    enabled: bool = True
    fault_mode: str = "POST_COMMIT_504"  # 'POST_COMMIT_504', 'POST_COMMIT_DROP', 'NONE'
    post_commit_delay_ms: float = 5.0
    max_faults_per_intent: int = 1
    fault_every_attempt: bool = False


@app.post("/debit")
def post_debit(req: DebitRequest):
    """
    POST /debit: Commits a transaction to the SQLite ledger.
    Note: If fault injection is active, the middleware intercepts the response
    AFTER commit and returns HTTP 504 Gateway Timeout.
    """
    try:
        commit_res = store.commit_debit(
            logical_operation_id=req.logical_operation_id,
            intent_id=req.intent_id,
            account_id=req.account_id,
            amount=req.amount,
        )
        return {
            "status": "COMMITTED",
            "commit": commit_res,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/operations/{identifier}")
def get_operation(identifier: str):
    """
    GET /operations/{identifier}:
    Authoritative out-of-band reconciliation endpoint.
    Returns ledger commits and current status for logical_operation_id or intent_id.
    """
    status = store.get_operation_status(identifier)
    return status


@app.post("/admin/fault-config")
def set_fault_config(cfg: FaultConfigRequest):
    """Sets the active fault injection policy."""
    fault_config.enabled = cfg.enabled
    fault_config.fault_mode = cfg.fault_mode
    fault_config.post_commit_delay_ms = cfg.post_commit_delay_ms
    fault_config.max_faults_per_intent = cfg.max_faults_per_intent
    fault_config.fault_every_attempt = cfg.fault_every_attempt
    fault_config.trigger_count = 0
    return {
        "status": "CONFIG_UPDATED",
        "fault_config": {
            "enabled": fault_config.enabled,
            "fault_mode": fault_config.fault_mode,
            "delay_ms": fault_config.post_commit_delay_ms,
            "fault_every_attempt": fault_config.fault_every_attempt,
        }
    }


@app.post("/admin/reset")
def reset_database(initial_balance: float = 10000.0):
    """Resets the store and account balance."""
    store.reset(initial_balance=initial_balance)
    fault_config.trigger_count = 0
    return {"status": "RESET_SUCCESS", "initial_balance": initial_balance}

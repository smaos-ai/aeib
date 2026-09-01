"""
Colibri RCE Governance Endpoint (SMAOS Layer 6)
POST /api/rce/check - Pre-execution model approval with fail-closed semantics
"""

import json
import logging
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import agentacct
try:
    from agentacct_capture import AgentAcct
except ImportError:
    AgentAcct = None

# Configure logging
LOG_DIR = Path(".gate-logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create file handler
file_handler = logging.FileHandler(LOG_DIR / "colibri_governance.log")
file_handler.setFormatter(logging.Formatter(
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())


class GovernanceState(str, Enum):
    """Governance decision states"""
    APPROVED = "approved"
    BLOCKED_MODEL = "blocked_model"
    BLOCKED_TOKENS = "blocked_tokens"
    BLOCKED_ACCESS = "blocked_access"
    BLOCKED_SEMANTIC = "blocked_semantic"
    ERROR = "error"


class RCECheckRequest(BaseModel):
    """Input schema for RCE check endpoint"""
    model_id: str = Field(..., description="Model identifier")
    prompt: str = Field(..., description="User prompt/query")
    context: Dict[str, Any] = Field(default_factory=dict, description="Request context")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier")


class RCECheckResponse(BaseModel):
    """Output schema for RCE check endpoint"""
    approved: bool
    reason: str
    governance_state: GovernanceState
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    execution_time_ms: float = 0.0


@dataclass
class GovernanceCheckResult:
    """Internal result structure"""
    approved: bool
    reason: str
    state: GovernanceState
    prompt_hash: str
    model_id: str
    timestamp: str


class ColibriGovernanceGate:
    """Fail-closed governance gate for Colibri model execution"""

    def __init__(self, policy_path: str = "config/colibri_governance_policy.json"):
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self._update_from_policy()

        # Initialize agentacct for work receipt tracking
        if AgentAcct:
            try:
                self.acct = AgentAcct()
            except Exception as e:
                logger.warning(f"Failed to initialize AgentAcct: {e}")
                self.acct = None
        else:
            logger.warning("AgentAcct not available, governance checks will not be logged")
            self.acct = None

    def _update_from_policy(self):
        """Update instance vars from policy dict"""
        self.approved_models = set(self.policy.get("approved_models", []))
        self.max_prompt_tokens = self.policy.get("max_prompt_tokens", 4096)
        self.semantic_guarantee = self.policy.get("semantic_guarantee", "strict_fp16")
        self.fail_closed = self.policy.get("fail_closed", True)

    def _load_policy(self) -> Dict[str, Any]:
        """Load governance policy from JSON config"""
        if not self.policy_path.exists():
            logger.error(f"Policy file not found: {self.policy_path}")
            return {"approved_models": [], "default_action": "DENY"}

        try:
            with open(self.policy_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load policy: {e}")
            return {"approved_models": [], "default_action": "DENY"}

    def _estimate_token_count(self, text: str) -> int:
        """Rough token estimation: ~4 chars per token"""
        return len(text) // 4

    def _hash_prompt(self, prompt: str) -> str:
        """SHA256 hash of prompt for audit trail"""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _check_model_id(self, model_id: str) -> tuple[bool, str]:
        """Check 1: Model ID against whitelist (FAIL-CLOSED)"""
        if model_id not in self.approved_models:
            reason = f"Model not whitelisted: {model_id}"
            logger.warning(f"BLOCK model_id check: {reason}")
            return False, reason
        return True, f"Model approved: {model_id}"

    def _check_prompt_length(self, prompt: str) -> tuple[bool, str]:
        """Check 2: Prompt token length (FAIL-CLOSED)"""
        token_count = self._estimate_token_count(prompt)
        if token_count > self.max_prompt_tokens:
            reason = f"Prompt exceeds {self.max_prompt_tokens} token limit ({token_count} estimated)"
            logger.warning(f"BLOCK prompt length check: {reason}")
            return False, reason
        return True, f"Prompt within limits ({token_count} tokens)"

    def _check_l3_permit_gate(self, user_id: Optional[str], tenant_id: Optional[str]) -> tuple[bool, str]:
        """Check 3: Query L3 permit gates (FAIL-CLOSED simulation)"""
        # Simulate L3 permit gate: default deny unless explicitly permitted
        if not user_id or not tenant_id:
            reason = "Access denied (L3 permit gate): missing user or tenant"
            logger.warning(f"BLOCK L3 gate check: {reason}")
            return False, reason

        # Whitelist for demo: allow specific user/tenant combinations
        permitted_pairs = {
            ("admin", "default"),
            ("user_001", "tenant_001"),
        }

        if (user_id, tenant_id) not in permitted_pairs:
            reason = f"Access denied (L3 permit gate): user {user_id} not permitted for tenant {tenant_id}"
            logger.warning(f"BLOCK L3 gate check: {reason}")
            return False, reason

        return True, f"User {user_id} permitted for tenant {tenant_id}"

    def _check_semantic_guarantee(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """Check 4: Semantic guarantee match (FAIL-CLOSED)"""
        config_semantic = context.get("semantic_guarantee", "strict_fp16")
        if config_semantic != self.semantic_guarantee:
            reason = f"Semantic guarantee mismatch: expected {self.semantic_guarantee}, got {config_semantic}"
            logger.warning(f"BLOCK semantic guarantee check: {reason}")
            return False, reason
        return True, f"Semantic guarantee matched: {self.semantic_guarantee}"

    def check(self, request: RCECheckRequest) -> GovernanceCheckResult:
        """Execute all pre-execution checks (fail-closed)"""
        start_time = time.time()
        prompt_hash = self._hash_prompt(request.prompt)
        timestamp = datetime.utcnow().isoformat()

        logger.info(f"RCE check initiated: model={request.model_id}, prompt_hash={prompt_hash}")

        # Check 1: Model ID whitelist
        passed, reason = self._check_model_id(request.model_id)
        if not passed:
            result = GovernanceCheckResult(
                approved=False,
                reason=reason,
                state=GovernanceState.BLOCKED_MODEL,
                prompt_hash=prompt_hash,
                model_id=request.model_id,
                timestamp=timestamp
            )
            self._log_to_agentacct(result, start_time)
            return result

        # Check 2: Prompt token length
        passed, reason = self._check_prompt_length(request.prompt)
        if not passed:
            result = GovernanceCheckResult(
                approved=False,
                reason=reason,
                state=GovernanceState.BLOCKED_TOKENS,
                prompt_hash=prompt_hash,
                model_id=request.model_id,
                timestamp=timestamp
            )
            self._log_to_agentacct(result, start_time)
            return result

        # Check 3: L3 permit gate
        passed, reason = self._check_l3_permit_gate(request.user_id, request.tenant_id)
        if not passed:
            result = GovernanceCheckResult(
                approved=False,
                reason=reason,
                state=GovernanceState.BLOCKED_ACCESS,
                prompt_hash=prompt_hash,
                model_id=request.model_id,
                timestamp=timestamp
            )
            self._log_to_agentacct(result, start_time)
            return result

        # Check 4: Semantic guarantee
        passed, reason = self._check_semantic_guarantee(request.context)
        if not passed:
            result = GovernanceCheckResult(
                approved=False,
                reason=reason,
                state=GovernanceState.BLOCKED_SEMANTIC,
                prompt_hash=prompt_hash,
                model_id=request.model_id,
                timestamp=timestamp
            )
            self._log_to_agentacct(result, start_time)
            return result

        # All checks passed
        result = GovernanceCheckResult(
            approved=True,
            reason="All governance checks passed",
            state=GovernanceState.APPROVED,
            prompt_hash=prompt_hash,
            model_id=request.model_id,
            timestamp=timestamp
        )
        self._log_to_agentacct(result, start_time)
        logger.info(f"RCE check APPROVED: model={request.model_id}, prompt_hash={prompt_hash}")
        return result

    def _log_to_agentacct(self, result: GovernanceCheckResult, start_time: float):
        """Log governance decision to agentacct work receipt"""
        if not self.acct:
            return

        try:
            self.acct.capture(
                action_id=f"colibri_rce_gate_{result.prompt_hash}",
                prompt=f"governance_check:{result.model_id}",
                tokens_used=0,
                cost=0.0
            )
        except Exception as e:
            logger.error(f"Failed to log to agentacct: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Colibri RCE Governance Gate",
    description="Layer 6 pre-execution model approval endpoint",
    version="1.0.0"
)

# Initialize governance gate (singleton)
_gate: Optional[ColibriGovernanceGate] = None


def get_gate() -> ColibriGovernanceGate:
    """Lazy-load governance gate"""
    global _gate
    if _gate is None:
        _gate = ColibriGovernanceGate()
    return _gate


@app.on_event("startup")
async def startup_event():
    """Initialize governance gate on startup"""
    gate = get_gate()
    logger.info("Colibri RCE governance gate ACTIVE")
    logger.info(f"Approved models: {gate.approved_models}")
    logger.info(f"Max prompt tokens: {gate.max_prompt_tokens}")
    logger.info(f"Semantic guarantee: {gate.semantic_guarantee}")


@app.post("/api/rce/check", response_model=RCECheckResponse)
async def check_rce_approval(request: RCECheckRequest) -> RCECheckResponse:
    """
    Pre-execution RCE governance check.

    Checks:
    1. Model ID against whitelist
    2. Prompt token length < 4096
    3. User/tenant access via L3 permit gates
    4. Semantic guarantee config match

    Returns: { approved: bool, reason: str, governance_state: str }
    Fail-closed: any check failure → approved=false
    """
    start_time = time.time()
    gate = get_gate()

    try:
        result = gate.check(request)

        execution_time_ms = (time.time() - start_time) * 1000

        if execution_time_ms > 100:
            logger.warning(f"Slow governance check: {execution_time_ms:.1f}ms")

        response = RCECheckResponse(
            approved=result.approved,
            reason=result.reason,
            governance_state=result.state,
            execution_time_ms=execution_time_ms
        )

        logger.info(f"RCE response: approved={response.approved}, state={response.governance_state}")
        return response

    except Exception as e:
        logger.error(f"Governance check error: {e}")

        # Fail-closed on error
        execution_time_ms = (time.time() - start_time) * 1000
        return RCECheckResponse(
            approved=False,
            reason=f"Governance check error: {str(e)}",
            governance_state=GovernanceState.ERROR,
            execution_time_ms=execution_time_ms
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "colibri_rce_gate",
        "timestamp": datetime.utcnow().isoformat()
    }


def start_governance_server(host: str = "127.0.0.1", port: int = 8000):
    """Start FastAPI server (for CLI integration)"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_governance_server()

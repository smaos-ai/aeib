"""OCR Audit Engine: Deterministic Hybrid Architecture for Agentic AI Security."""

from ocr_audit.dispatcher import DeterministicDispatcher, TraceRecord, DispatchMetrics
from ocr_audit.bundler import SmartActionBundler, ActionBundle
from ocr_audit.interrogator import ForensicInterrogator, CandidateFinding
from ocr_audit.reflector import WireTruthReflector, VerifiedAuditFinding
from ocr_audit.anchor import DeterministicAnchor
from ocr_audit.pipeline_runner import HybridAuditPipeline
from ocr_audit.saga_reconciler import SagaReconciler
from ocr_audit.kms_enclave import HardwareAttestationKMS
from ocr_audit.rce_cockpit import RceCockpit
from ocr_audit.psi_circuit_breaker import PsiCircuitBreaker
from ocr_audit.capability_attenuation import CapabilityAttenuator
from ocr_audit.offline_ast_updater import OfflineAstHeuristicUpdater
from ocr_audit.kernel_omission_enforcer import KernelOmissionEnforcer
from ocr_audit.pre_access_gate import PreAccessComplianceGate
from ocr_audit import moats

__version__ = "1.3.0"

__all__ = [
    "DeterministicDispatcher",
    "TraceRecord",
    "DispatchMetrics",
    "SmartActionBundler",
    "ActionBundle",
    "ForensicInterrogator",
    "CandidateFinding",
    "WireTruthReflector",
    "VerifiedAuditFinding",
    "DeterministicAnchor",
    "HybridAuditPipeline",
    "SagaReconciler",
    "HardwareAttestationKMS",
    "RceCockpit",
    "PsiCircuitBreaker",
    "CapabilityAttenuator",
    "OfflineAstHeuristicUpdater",
    "KernelOmissionEnforcer",
    "PreAccessComplianceGate",
    "moats",
]

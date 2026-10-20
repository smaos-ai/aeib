// Copyright 2026 SovereignNexus Project
// crates/aeib-ebpf-lsm/src/controller.rs
//
// Userspace controller for AEIB eBPF LSM policy maps and Ring 0 event consumption.
// Provides both Aya-compatible kernel map loader on Linux and deterministic clean-room
// evaluation on macOS/Darwin test runners.
//
// Epistemic Status: Evaluated and tested under prototype execution model.

use crate::types::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

#[derive(Error, Debug, PartialEq, Eq)]
pub enum EbpfGuardError {
    #[error("Executable binary not permitted: inode {0}")]
    ExecutableNotPermitted(u64),

    #[error("Executable binary hash mismatch for inode {0}")]
    BinaryDigestMismatch(u64),

    #[error("W^X violation: simultaneous write and execute permissions requested (prot: {0:#x})")]
    MemoryWxViolation(u32),

    #[error("Model tensor weight fingerprint mismatch for inode {0}")]
    ModelWeightDigestMismatch(u64),

    #[error("Socket egress denied: tainted agent pid {0} cannot open external connection")]
    SocketEgressDenied(u32),

    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),
}

/// In-memory state tracking for eBPF maps and audit ring buffer
#[derive(Default)]
struct EbpfState {
    allowed_executables: HashMap<u64, AgentExecPolicy>,
    tensor_weights: HashMap<u64, TensorWeightMeasurement>,
    agent_taint: HashMap<u32, AgentProcessTaint>,
    socket_rules: HashMap<u64, SocketFilterRule>,
    ringbuf_events: Vec<ScittRingBufEvent>,
}

#[derive(Clone)]
pub struct EbpfAgentGuardController {
    state: Arc<Mutex<EbpfState>>,
}

impl Default for EbpfAgentGuardController {
    fn default() -> Self {
        Self::new()
    }
}

impl EbpfAgentGuardController {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(EbpfState::default())),
        }
    }

    fn now_ns() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64
    }

    /// Pin an allowed binary executable by its filesystem inode and SHA-256 digest
    pub fn allow_executable(
        &self,
        inode: u64,
        expected_sha256: [u8; 32],
        max_perms: u32,
    ) {
        let mut state = self.state.lock().unwrap();
        state.allowed_executables.insert(
            inode,
            AgentExecPolicy {
                inode,
                expected_sha256,
                max_perms,
                _pad: 0,
            },
        );
    }

    /// Register verified model weight tensor fingerprints
    pub fn register_tensor_weights(
        &self,
        inode: u64,
        offset: u64,
        length: u64,
        expected_sha256: [u8; 32],
    ) {
        let mut state = self.state.lock().unwrap();
        state.tensor_weights.insert(
            inode,
            TensorWeightMeasurement {
                inode,
                offset,
                length,
                expected_sha256,
            },
        );
    }

    /// Set process taint level and spend consequence ceiling
    pub fn set_process_taint(
        &self,
        pid: u32,
        taint_tier: u32,
        max_consequence_minor: u64,
    ) {
        let mut state = self.state.lock().unwrap();
        state.agent_taint.insert(
            pid,
            AgentProcessTaint {
                pid,
                taint_tier,
                max_consequence_minor,
            },
        );
    }

    /// Configure socket filter policy
    pub fn set_socket_rule(
        &self,
        ipv4_addr: u32,
        port: u16,
        protocol: u8,
        action: u8,
    ) {
        let key = ((ipv4_addr as u64) << 32) | ((port as u64) << 16) | (protocol as u64);
        let mut state = self.state.lock().unwrap();
        state.socket_rules.insert(
            key,
            SocketFilterRule {
                ipv4_addr,
                port,
                protocol,
                action,
            },
        );
    }

    /// Hook evaluation: bprm_check_security
    pub fn check_bprm_security(
        &self,
        pid: u32,
        inode: u64,
        actual_sha256: &[u8; 32],
    ) -> Result<(), EbpfGuardError> {
        let mut state = self.state.lock().unwrap();
        let policy = state
            .allowed_executables
            .get(&inode)
            .copied()
            .ok_or(EbpfGuardError::ExecutableNotPermitted(inode))?;

        if &policy.expected_sha256 != actual_sha256 {
            let event = ScittRingBufEvent {
                timestamp_ns: Self::now_ns(),
                pid,
                hook_id: HOOK_BPRM_CHECK_SECURITY,
                status_code: VERDICT_EPERM,
                _pad: 0,
                event_digest: *actual_sha256,
            };
            state.ringbuf_events.push(event);
            return Err(EbpfGuardError::BinaryDigestMismatch(inode));
        }

        let event = ScittRingBufEvent {
            timestamp_ns: Self::now_ns(),
            pid,
            hook_id: HOOK_BPRM_CHECK_SECURITY,
            status_code: VERDICT_ALLOW,
            _pad: 0,
            event_digest: *actual_sha256,
        };
        state.ringbuf_events.push(event);
        Ok(())
    }

    /// Hook evaluation: file_mprotect (W^X memory isolation)
    pub fn check_mprotect(&self, pid: u32, prot: u32) -> Result<(), EbpfGuardError> {
        let prot_write = 0x2u32;
        let prot_exec = 0x4u32;

        if (prot & prot_write != 0) && (prot & prot_exec != 0) {
            let mut state = self.state.lock().unwrap();
            let event = ScittRingBufEvent {
                timestamp_ns: Self::now_ns(),
                pid,
                hook_id: HOOK_FILE_MPROTECT,
                status_code: VERDICT_EACCES,
                _pad: 0,
                event_digest: [0u8; 32],
            };
            state.ringbuf_events.push(event);
            return Err(EbpfGuardError::MemoryWxViolation(prot));
        }

        let mut state = self.state.lock().unwrap();
        let event = ScittRingBufEvent {
            timestamp_ns: Self::now_ns(),
            pid,
            hook_id: HOOK_FILE_MPROTECT,
            status_code: VERDICT_ALLOW,
            _pad: 0,
            event_digest: [0u8; 32],
        };
        state.ringbuf_events.push(event);
        Ok(())
    }

    /// Hook evaluation: mmap_file tensor weight validation
    pub fn check_mmap_weights(
        &self,
        pid: u32,
        inode: u64,
        offset: u64,
        length: u64,
        actual_sha256: &[u8; 32],
    ) -> Result<(), EbpfGuardError> {
        let mut state = self.state.lock().unwrap();
        if let Some(measurement) = state.tensor_weights.get(&inode).copied() {
            if measurement.offset == offset
                && measurement.length == length
                && &measurement.expected_sha256 != actual_sha256
            {
                let event = ScittRingBufEvent {
                    timestamp_ns: Self::now_ns(),
                    pid,
                    hook_id: HOOK_MMAP_FILE,
                    status_code: VERDICT_EPERM,
                    _pad: 0,
                    event_digest: *actual_sha256,
                };
                state.ringbuf_events.push(event);
                return Err(EbpfGuardError::ModelWeightDigestMismatch(inode));
            }
        }

        let event = ScittRingBufEvent {
            timestamp_ns: Self::now_ns(),
            pid,
            hook_id: HOOK_MMAP_FILE,
            status_code: VERDICT_ALLOW,
            _pad: 0,
            event_digest: *actual_sha256,
        };
        state.ringbuf_events.push(event);
        Ok(())
    }

    /// Hook evaluation: socket_connect egress defense
    pub fn check_socket_connect(
        &self,
        pid: u32,
        dest_ip: u32,
        dest_port: u16,
    ) -> Result<(), EbpfGuardError> {
        let mut state = self.state.lock().unwrap();

        // 1. Check if process is tainted as untrusted agent (forcing host proxy sidecar)
        if let Some(taint) = state.agent_taint.get(&pid).copied() {
            if taint.taint_tier == TAINT_TIER_2_UNTRUSTED {
                let event = ScittRingBufEvent {
                    timestamp_ns: Self::now_ns(),
                    pid,
                    hook_id: HOOK_SOCKET_CONNECT,
                    status_code: VERDICT_EPERM,
                    _pad: 0,
                    event_digest: [0u8; 32],
                };
                state.ringbuf_events.push(event);
                return Err(EbpfGuardError::SocketEgressDenied(pid));
            }
        }

        // 2. Check explicit socket filter rules (protocol 6 = TCP)
        let key = ((dest_ip as u64) << 32) | ((dest_port as u64) << 16) | 6u64;
        if let Some(rule) = state.socket_rules.get(&key).copied() {
            if rule.action == ACTION_DENY {
                let event = ScittRingBufEvent {
                    timestamp_ns: Self::now_ns(),
                    pid,
                    hook_id: HOOK_SOCKET_CONNECT,
                    status_code: VERDICT_EPERM,
                    _pad: 0,
                    event_digest: [0u8; 32],
                };
                state.ringbuf_events.push(event);
                return Err(EbpfGuardError::SocketEgressDenied(pid));
            }
        }

        let event = ScittRingBufEvent {
            timestamp_ns: Self::now_ns(),
            pid,
            hook_id: HOOK_SOCKET_CONNECT,
            status_code: VERDICT_ALLOW,
            _pad: 0,
            event_digest: [0u8; 32],
        };
        state.ringbuf_events.push(event);
        Ok(())
    }

    /// Retrieve recorded SCITT audit ring buffer events
    pub fn drain_audit_events(&self) -> Vec<ScittRingBufEvent> {
        let mut state = self.state.lock().unwrap();
        std::mem::take(&mut state.ringbuf_events)
    }

    /// Total event count
    pub fn event_count(&self) -> usize {
        let state = self.state.lock().unwrap();
        state.ringbuf_events.len()
    }
}

// Copyright 2026 SovereignNexus Project
// crates/aeib-ebpf-lsm/src/types.rs
//
// Shared C-ABI structs and serialization models for AEIB eBPF LSM maps and events.
// Epistemic Status: Evaluated and tested under prototype execution model.

use serde::{Deserialize, Serialize};

pub const HOOK_BPRM_CHECK_SECURITY: u32 = 1;
pub const HOOK_FILE_MPROTECT: u32 = 2;
pub const HOOK_MMAP_FILE: u32 = 3;
pub const HOOK_SOCKET_CONNECT: u32 = 4;

pub const VERDICT_ALLOW: i32 = 0;
pub const VERDICT_EPERM: i32 = -1;
pub const VERDICT_EACCES: i32 = -13;

pub const TAINT_TIER_0_SYSTEM: u32 = 0;
pub const TAINT_TIER_1_PARTNER: u32 = 1;
pub const TAINT_TIER_2_UNTRUSTED: u32 = 2;

pub const ACTION_DENY: u8 = 0;
pub const ACTION_ALLOW: u8 = 1;

/// C-ABI compatible binary allowlist entry stored in BPF hash map `ALLOWED_EXECUTABLES`
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentExecPolicy {
    pub inode: u64,
    pub expected_sha256: [u8; 32],
    pub max_perms: u32,
    pub _pad: u32,
}

/// C-ABI compatible model tensor weight measurement in BPF hash map `TENSOR_WEIGHT_DIGESTS`
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TensorWeightMeasurement {
    pub inode: u64,
    pub offset: u64,
    pub length: u64,
    pub expected_sha256: [u8; 32],
}

/// C-ABI compatible agent process taint state in BPF hash map `AGENT_TAINT_MAP`
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentProcessTaint {
    pub pid: u32,
    pub taint_tier: u32,
    pub max_consequence_minor: u64,
}

/// C-ABI compatible socket egress filter rule in BPF hash map `ALLOWED_SOCKET_ENDPOINTS`
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SocketFilterRule {
    pub ipv4_addr: u32,
    pub port: u16,
    pub protocol: u8,
    pub action: u8,
}

/// C-ABI compatible audit record emitted to BPF ring buffer `SCITT_AUDIT_RINGBUF`
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScittRingBufEvent {
    pub timestamp_ns: u64,
    pub pid: u32,
    pub hook_id: u32,
    pub status_code: i32,
    pub _pad: u32,
    pub event_digest: [u8; 32],
}

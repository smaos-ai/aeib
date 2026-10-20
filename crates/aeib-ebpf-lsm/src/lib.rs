// Copyright 2026 SovereignNexus Project
// crates/aeib-ebpf-lsm/src/lib.rs
//
// AEIB Kernel eBPF LSM Policy Engine and Userspace Controller.
//
// Epistemic Boundary Notice:
// All components in this crate describe properties observed, tested, evaluated,
// and configured under the stated model of our local prototype and test harness.
// On Linux systems with CONFIG_BPF_LSM=y, these structures target Aya CO-RE bytecode.
// On non-Linux or unprivileged test environments, a clean-room in-memory simulation
// controller evaluates identical state machine invariants.

pub mod bpf;
pub mod controller;
pub mod types;

pub use controller::{EbpfAgentGuardController, EbpfGuardError};
pub use types::*;

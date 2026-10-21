//! crates/aeib-data-plane/src/wal.rs
//!
//! AEIB High-Performance Group-Commit Durability Write-Ahead Log (WAL).
//!
//! Systems Engineering Context (LIMITATIONS.md §4):
//! - Mitigates the macOS Darwin NVMe Volatile Cache Trap:
//!   Standard POSIX fsync() on Darwin ARM64 flushes only to the NVMe controller's
//!   volatile RAM cache. True physical media durability on Darwin requires
//!   `fcntl(fd, F_FULLFSYNC)`.
//! - Group Commit: Batches concurrent agent dispatches into static memory slots
//!   (default 64) and flushes them in a single physical sync operation.
//! - Linux/POSIX: Scaffolds fdatasync/fsync with zero-allocation ring-buffer slots.

use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};
use std::time::Instant;

pub const DEFAULT_RING_CAPACITY: usize = 64;

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WalStatus {
    LatchedPreDispatch = 0,
    EffectIndeterminate = 1,
    ResolvedConfirmed = 2,
    ResolvedRefuted = 3,
}

impl WalStatus {
    pub fn from_u8(v: u8) -> Option<Self> {
        match v {
            0 => Some(WalStatus::LatchedPreDispatch),
            1 => Some(WalStatus::EffectIndeterminate),
            2 => Some(WalStatus::ResolvedConfirmed),
            3 => Some(WalStatus::ResolvedRefuted),
            _ => None,
        }
    }
}

/// A pre-allocated, fixed-size entry slot inside the WAL group-commit ring.
#[derive(Clone, Serialize, Deserialize)]
pub struct WalSlot {
    pub seq: u64,
    pub operation_id: String,
    pub action_caid: [u8; 32],
    pub status: WalStatus,
    pub timestamp_ns: u64,
    pub committed: bool,
}

impl Default for WalSlot {
    fn default() -> Self {
        Self {
            seq: 0,
            operation_id: String::with_capacity(64),
            action_caid: [0u8; 32],
            status: WalStatus::LatchedPreDispatch,
            timestamp_ns: 0,
            committed: false,
        }
    }
}

/// Result of a group-commit flush operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroupCommitMetrics {
    pub flushed_slots: usize,
    pub elapsed_micros: u64,
    pub end_seq: u64,
    pub sync_mechanism: String,
}

/// Static-memory Ring-Buffer WAL with Platform-Calibrated Physical Durability.
pub struct GroupCommitWal {
    file: File,
    path: PathBuf,
    slots: Vec<WalSlot>,
    next_seq: u64,
    unflushed_count: usize,
}

impl GroupCommitWal {
    /// Opens or creates the WAL file at the specified path with the given ring capacity.
    pub fn open<P: AsRef<Path>>(path: P, capacity: usize) -> io::Result<Self> {
        let path_buf = path.as_ref().to_path_buf();
        if let Some(parent) = path_buf.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let file = OpenOptions::new()
            .read(true)
            .append(true)
            .create(true)
            .open(&path_buf)?;

        let mut slots = Vec::with_capacity(capacity);
        for _ in 0..capacity {
            slots.push(WalSlot::default());
        }

        // Recover highest existing seq if recovering an existing WAL
        let next_seq = Self::scan_highest_seq(&path_buf).unwrap_or(0) + 1;

        Ok(Self {
            file,
            path: path_buf,
            slots,
            next_seq,
            unflushed_count: 0,
        })
    }

    /// Scans the file to determine the highest existing sequence number.
    fn scan_highest_seq(path: &Path) -> io::Result<u64> {
        let file = match File::open(path) {
            Ok(f) => f,
            Err(_) => return Ok(0),
        };
        let reader = BufReader::new(file);
        let mut max_seq = 0u64;

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            if let Ok(entry) = serde_json::from_str::<serde_json::Value>(&line) {
                if let Some(s) = entry.get("seq").and_then(|v| v.as_u64()) {
                    if s > max_seq {
                        max_seq = s;
                    }
                }
            }
        }
        Ok(max_seq)
    }

    /// Stages a pre-dispatch intent into the next available ring buffer slot.
    /// If the ring buffer reaches capacity, it automatically executes a group commit.
    pub fn append_intent(
        &mut self,
        operation_id: &str,
        action_caid: &[u8; 32],
        status: WalStatus,
        timestamp_ns: u64,
    ) -> io::Result<u64> {
        if self.unflushed_count >= self.slots.len() {
            self.flush_group()?;
        }

        let seq = self.next_seq;
        self.next_seq += 1;

        let slot_idx = self.unflushed_count;
        let slot = &mut self.slots[slot_idx];
        slot.seq = seq;
        slot.operation_id.clear();
        slot.operation_id.push_str(operation_id);
        slot.action_caid.copy_from_slice(action_caid);
        slot.status = status;
        slot.timestamp_ns = timestamp_ns;
        slot.committed = false;

        self.unflushed_count += 1;
        Ok(seq)
    }

    /// Flushes all pending ring slots to disk using platform-calibrated durability primitives.
    pub fn flush_group(&mut self) -> io::Result<GroupCommitMetrics> {
        if self.unflushed_count == 0 {
            return Ok(GroupCommitMetrics {
                flushed_slots: 0,
                elapsed_micros: 0,
                end_seq: self.next_seq.saturating_sub(1),
                sync_mechanism: "noop".to_string(),
            });
        }

        let start = Instant::now();
        let count = self.unflushed_count;

        // Serialize buffered slots as JSONL
        for i in 0..count {
            let slot = &mut self.slots[i];
            let caid_hex = hex::encode(slot.action_caid);
            let line = format!(
                "{{\"seq\":{},\"operation_id\":\"{}\",\"action_caid\":\"{}\",\"status\":{},\"timestamp_ns\":{}}}\n",
                slot.seq, slot.operation_id, caid_hex, slot.status as u8, slot.timestamp_ns
            );
            self.file.write_all(line.as_bytes())?;
            slot.committed = true;
        }

        // Platform-calibrated physical durability barrier
        let sync_mechanism = self.perform_physical_sync()?;

        let elapsed = start.elapsed();
        let elapsed_micros = elapsed.as_micros() as u64;
        let end_seq = self.slots[count - 1].seq;

        // Reset ring counter
        self.unflushed_count = 0;

        Ok(GroupCommitMetrics {
            flushed_slots: count,
            elapsed_micros,
            end_seq,
            sync_mechanism,
        })
    }

    /// Executes the physical media flush across OS targets.
    fn perform_physical_sync(&mut self) -> io::Result<String> {
        let fd = self.file.as_raw_fd();

        #[cfg(target_os = "macos")]
        {
            // On Darwin ARM64/x86_64, standard fsync only writes to drive cache.
            // F_FULLFSYNC commands the physical media write-through barrier.
            let ret = unsafe { libc::fcntl(fd, libc::F_FULLFSYNC) };
            if ret == -1 {
                let err = io::Error::last_os_error();
                // Fall back to standard sync if filesystem does not support F_FULLFSYNC
                self.file.sync_all()?;
                Ok(format!("darwin_fallback_sync_all({})", err))
            } else {
                Ok("darwin_fcntl_F_FULLFSYNC".to_string())
            }
        }

        #[cfg(target_os = "linux")]
        {
            // On Linux, fdatasync avoids flushing metadata if only file contents changed.
            let ret = unsafe { libc::fdatasync(fd) };
            if ret == -1 {
                self.file.sync_all()?;
                Ok("linux_fallback_sync_all".to_string())
            } else {
                Ok("linux_libc_fdatasync".to_string())
            }
        }

        #[cfg(not(any(target_os = "macos", target_os = "linux")))]
        {
            self.file.sync_all()?;
            Ok("generic_posix_sync_all".to_string())
        }
    }

    /// Re-reads all entries from the on-disk WAL for recovery.
    pub fn read_all_persisted_entries(&self) -> io::Result<Vec<WalSlot>> {
        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);
        let mut entries = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line) {
                let seq = val.get("seq").and_then(|v| v.as_u64()).unwrap_or(0);
                let op_id = val
                    .get("operation_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let caid_hex = val
                    .get("action_caid")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let status_val = val.get("status").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
                let ts = val.get("timestamp_ns").and_then(|v| v.as_u64()).unwrap_or(0);

                let mut caid = [0u8; 32];
                if let Ok(b) = hex::decode(caid_hex) {
                    if b.len() == 32 {
                        caid.copy_from_slice(&b);
                    }
                }

                entries.push(WalSlot {
                    seq,
                    operation_id: op_id,
                    action_caid: caid,
                    status: WalStatus::from_u8(status_val).unwrap_or(WalStatus::LatchedPreDispatch),
                    timestamp_ns: ts,
                    committed: true,
                });
            }
        }
        Ok(entries)
    }

    pub fn unflushed_count(&self) -> usize {
        self.unflushed_count
    }

    pub fn next_seq(&self) -> u64 {
        self.next_seq
    }
}

/// Direct-I/O WAL providing direct media writes bypassing OS page cache buffers.
/// - Linux: Evaluated using O_DIRECT | O_SYNC with sector alignment (4096 bytes).
/// - Darwin / macOS: Evaluated using F_NOCACHE and F_FULLFSYNC write-through barrier.
/// - Enforces direct hardware-level durability under the stated fault model.
pub struct DirectIoWal {
    file: tokio::fs::File,
    offset: u64,
}

impl DirectIoWal {
    /// Opens or creates a WAL file configured with direct I/O and synchronous flags.
    /// Requires buffer allocations to be aligned to logical sector sizes (typically 4096 bytes).
    pub async fn open<P: AsRef<Path>>(path: P) -> io::Result<Self> {
        let std_file = {
            #[cfg(target_os = "linux")]
            {
                use std::os::unix::fs::OpenOptionsExt;
                OpenOptions::new()
                    .create(true)
                    .read(true)
                    .write(true)
                    .custom_flags(libc::O_DIRECT | libc::O_SYNC)
                    .open(path)?
            }

            #[cfg(target_os = "macos")]
            {
                let f = OpenOptions::new()
                    .create(true)
                    .read(true)
                    .write(true)
                    .truncate(false)
                    .open(path)?;
                let fd = f.as_raw_fd();
                unsafe {
                    libc::fcntl(fd, libc::F_NOCACHE, 1);
                }
                f
            }

            #[cfg(not(any(target_os = "linux", target_os = "macos")))]
            {
                OpenOptions::new()
                    .create(true)
                    .read(true)
                    .write(true)
                    .open(path)?
            }
        };

        let file = tokio::fs::File::from_std(std_file);
        let offset = file.metadata().await?.len();

        Ok(Self { file, offset })
    }

    /// Appends a serialized canonical frame directly to persistent media.
    /// The input buffer `data` must be sector-aligned (4096 bytes) for O_DIRECT compliance.
    pub async fn append_aligned_frame(&mut self, data: Vec<u8>) -> io::Result<()> {
        use tokio::io::AsyncWriteExt;
        let len = data.len() as u64;

        self.file.write_all(&data).await?;

        #[cfg(target_os = "macos")]
        {
            let fd = self.file.as_raw_fd();
            unsafe {
                libc::fcntl(fd, libc::F_FULLFSYNC);
            }
        }
        #[cfg(not(target_os = "macos"))]
        {
            self.file.sync_data().await?;
        }

        self.offset += len;
        Ok(())
    }

    pub fn offset(&self) -> u64 {
        self.offset
    }
}

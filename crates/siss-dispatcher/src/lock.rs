//! File-based distributed locking for queue coordination
//!
//! Uses lockfiles to prevent concurrent modifications to shared state.
//! Supports timeout-based lock acquisition.

use crate::{DispatchError, Result};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};
use tokio::fs;
use tokio::time::sleep;

/// File-based lock guard
pub struct FileLock {
    path: PathBuf,
}

impl FileLock {
    /// Acquire a lock with timeout
    pub async fn acquire<P: AsRef<Path>>(
        path: P,
        timeout: Duration,
    ) -> Result<Self> {
        let path = path.as_ref().to_path_buf();
        let start = Instant::now();

        loop {
            // Check if lock already exists
            if path.exists() {
                if start.elapsed() > timeout {
                    return Err(DispatchError::LockTimeout);
                }
                // TODO: Check lock age and implement stale lock cleanup
                sleep(Duration::from_millis(100)).await;
                continue;
            }

            // Try to create lock file atomically
            match std::fs::OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(&path)
            {
                Ok(_) => return Ok(Self { path }),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                    if start.elapsed() > timeout {
                        return Err(DispatchError::LockTimeout);
                    }
                    sleep(Duration::from_millis(100)).await;
                }
                Err(e) => return Err(DispatchError::LockError(e.to_string())),
            }
        }
    }

    /// Release the lock
    pub async fn release(self) -> Result<()> {
        fs::remove_file(&self.path).await?;
        Ok(())
    }
}

impl Drop for FileLock {
    fn drop(&mut self) {
        // Best-effort cleanup on drop
        // TODO: Implement async-aware drop
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn test_lock_acquire_and_release() {
        let tempdir = tempfile::tempdir().unwrap();
        let lock_path = tempdir.path().join("test.lock");

        let lock = FileLock::acquire(&lock_path, Duration::from_secs(5))
            .await
            .expect("Failed to acquire lock");

        assert!(lock_path.exists());

        lock.release().await.expect("Failed to release lock");
        assert!(!lock_path.exists());
    }

    #[tokio::test]
    async fn test_lock_conflict_detection() {
        // Test that when a lock file exists, acquisition fails
        let tempdir = tempfile::tempdir().unwrap();
        let lock_path = tempdir.path().join("conflict.lock");

        // Pre-create lock file to simulate contention
        fs::write(&lock_path, "locked").await.unwrap();

        // Attempting to acquire should fail immediately (file exists)
        let result = FileLock::acquire(&lock_path, Duration::from_millis(50)).await;

        // Should fail with lock error or timeout
        assert!(result.is_err());

        // Clean up
        fs::remove_file(&lock_path).await.ok();
    }
}

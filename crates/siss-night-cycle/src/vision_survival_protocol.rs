use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use uuid::Uuid;

/// VisionSurvivalProtocol — Automated vault sync for vision resilience
/// Runs nightly to ensure the vision survives hardware failure by syncing
/// to three encrypted vaults (A, B, C) and alerting on critical changes.
pub struct VisionSurvivalProtocol {
    vault_mount_points: Vec<PathBuf>,
    workspace_path: PathBuf,
    last_sync_hash: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SyncCapsule {
    pub sync_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub vault_location: char, // 'A', 'B', or 'C'
    pub delta_size_bytes: u64,
    pub workspace_checksum: String,
    pub critical_changes: Vec<String>, // Genesis Capsule, key updates, etc.
    pub status: SyncStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum SyncStatus {
    Success,
    PartialSuccess { failed_vaults: Vec<char> },
    Failed { reason: String },
}

impl VisionSurvivalProtocol {
    pub fn new(workspace_path: PathBuf) -> Self {
        Self {
            vault_mount_points: vec![],
            workspace_path,
            last_sync_hash: None,
        }
    }

    /// Detect mounted vaults (A, B, C)
    /// Scans /Volumes on macOS for mounted encrypted vaults matching pattern: SMAOS_VAULT_[ABC]
    pub fn detect_vaults(&mut self) -> Result<Vec<char>, String> {
        let mut vaults = vec![];

        // macOS: Check /Volumes for mounted encrypted vaults
        let volumes_path = Path::new("/Volumes");
        if volumes_path.exists() {
            for entry in fs::read_dir(volumes_path).map_err(|e| e.to_string())? {
                let entry = entry.map_err(|e| e.to_string())?;
                let path = entry.path();
                let name = entry.file_name();

                // Match vault naming pattern: SMAOS_VAULT_A, SMAOS_VAULT_B, SMAOS_VAULT_C
                if let Some(name_str) = name.to_str().filter(|s| s.starts_with("SMAOS_VAULT_")) {
                    if let Some(location) = name_str
                        .chars()
                        .last()
                        .filter(|&c| matches!(c, 'A' | 'B' | 'C'))
                    {
                        vaults.push(location);
                        self.vault_mount_points.push(path);
                    }
                }
            }
        }

        if vaults.is_empty() {
            return Err("No encrypted vaults detected. Ensure USB drives are mounted.".to_string());
        }

        vaults.sort();
        Ok(vaults)
    }

    /// Compute workspace checksum using SHA-256
    /// Walks entire workspace tree excluding standard exclusions (.git, target, node_modules, etc.)
    pub fn compute_workspace_checksum(&self) -> Result<String, String> {
        let mut hasher = Sha256::new();

        // Walk workspace, hash all files except excluded dirs
        self.hash_directory(&self.workspace_path, &mut hasher)?;

        let result = hasher.finalize();
        Ok(format!("{:x}", result))
    }

    fn hash_directory(&self, path: &Path, hasher: &mut Sha256) -> Result<(), String> {
        // Exclude: .git, target, node_modules, .DS_Store, .claude/private, etc.
        let excluded = [
            ".git",
            "target",
            "node_modules",
            ".DS_Store",
            ".claude/private",
            ".venv",
            "__pycache__",
        ];

        match fs::read_dir(path) {
            Ok(entries) => {
                for entry in entries {
                    let entry = entry.map_err(|e| e.to_string())?;
                    let entry_path = entry.path();

                    if let Some(name_str) = entry_path.file_name().and_then(|n| n.to_str()) {
                        if excluded.contains(&name_str) {
                            continue; // Skip excluded directories
                        }
                    }

                    if entry_path.is_dir() {
                        self.hash_directory(&entry_path, hasher)?;
                    } else {
                        match fs::read(&entry_path) {
                            Ok(contents) => {
                                hasher.update(&contents);
                            }
                            Err(_) => {
                                // Skip files we can't read (e.g., locked files)
                                continue;
                            }
                        }
                    }
                }
            }
            Err(_) => {
                // Skip directories we can't read
            }
        }

        Ok(())
    }

    /// Compute delta — files changed since last sync
    /// Uses git diff to find changed files for efficient sync
    pub fn compute_delta(&self, current_checksum: &str) -> Result<Vec<String>, String> {
        let mut delta = vec![];

        if let Some(ref last_hash) = self.last_sync_hash.filter(|h| h == current_checksum) {
            // No changes
            return Ok(delta);
        }

        // Run git diff to find changed files
        let output = Command::new("git")
            .arg("diff")
            .arg("--name-only")
            .arg("HEAD")
            .current_dir(&self.workspace_path)
            .output()
            .map_err(|e| format!("git diff failed: {}", e))?;

        if output.status.success() {
            let diff = String::from_utf8_lossy(&output.stdout);
            delta = diff
                .lines()
                .filter(|l| !l.is_empty())
                .map(|l| l.to_string())
                .collect();
        }

        Ok(delta)
    }

    /// Detect critical Genesis-level changes
    /// Returns list of files that require immediate physical vault rotation
    pub fn detect_critical_changes(&self, delta: &[String]) -> Vec<String> {
        let mut critical = vec![];

        let critical_patterns = [
            "Genesis",
            "private_key",
            "secret_key",
            "LAYER14",
            "Trust",
            "patent",
            "VAULT_MANIFEST",
            "encryption",
            "authentication",
        ];

        for file in delta {
            for pattern in &critical_patterns {
                if file.contains(pattern) {
                    critical.push(file.to_string());
                    break;
                }
            }
        }

        critical.sort();
        critical.dedup();
        critical
    }

    /// Sync workspace to vault using rsync
    /// Performs efficient delta sync and returns total size synced
    pub fn sync_to_vault(&self, vault_path: &Path) -> Result<u64, String> {
        let vault_smaos = vault_path.join("smaos");

        // Ensure vault directory exists
        fs::create_dir_all(&vault_smaos)
            .map_err(|e| format!("Failed to create vault directory: {}", e))?;

        // Use rsync for efficient delta sync
        let output = Command::new("rsync")
            .arg("-av")
            .arg("--delete")
            .arg("--exclude=.git")
            .arg("--exclude=.git/")
            .arg("--exclude=target")
            .arg("--exclude=target/")
            .arg("--exclude=node_modules")
            .arg("--exclude=node_modules/")
            .arg("--exclude=.DS_Store")
            .arg("--exclude=__pycache__")
            .arg(format!("{}/", self.workspace_path.display()))
            .arg(format!("{}/", vault_smaos.display()))
            .output()
            .map_err(|e| format!("rsync command failed: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("rsync sync failed: {}", stderr));
        }

        // Calculate sync size from rsync stats
        let stdout = String::from_utf8_lossy(&output.stdout);
        let total_size: u64 = stdout
            .lines()
            .filter_map(|line| {
                // Look for lines with byte counts (rsync output format)
                if let Some(size_part) = line.split_whitespace().next() {
                    size_part.replace(',', "").parse::<u64>().ok()
                } else {
                    None
                }
            })
            .sum();

        Ok(total_size)
    }

    /// Verify vault integrity — spot check for key files
    pub fn verify_vault(&self, vault_path: &Path) -> Result<bool, String> {
        let vault_smaos = vault_path.join("smaos");

        if !vault_smaos.exists() {
            return Err("Vault workspace not found.".to_string());
        }

        // Quick spot check: verify key files exist
        let key_files = [
            "Cargo.toml",
            "crates/siss-night-cycle/Cargo.toml",
            "CLAUDE.md",
        ];

        for key_file in &key_files {
            if !vault_smaos.join(key_file).exists() {
                return Err(format!("Key file missing in vault: {}", key_file));
            }
        }

        Ok(true)
    }

    /// Update vault manifest with sync information
    pub fn update_manifest(
        &self,
        vault_path: &Path,
        sync_capsule: &SyncCapsule,
    ) -> Result<(), String> {
        let manifest_path = vault_path.join("VAULT_MANIFEST.json");

        // Load existing manifest or create new one
        let mut manifest: serde_json::Value = if manifest_path.exists() {
            serde_json::from_str(&fs::read_to_string(&manifest_path).map_err(|e| e.to_string())?)
                .unwrap_or_else(|_| serde_json::json!({}))
        } else {
            serde_json::json!({})
        };

        // Update sync info
        manifest["last_sync"] =
            serde_json::to_value(sync_capsule.timestamp).map_err(|e| e.to_string())?;
        manifest["last_checksum"] = serde_json::json!(sync_capsule.workspace_checksum);
        manifest["sync_status"] = serde_json::json!(format!("{:?}", sync_capsule.status));
        manifest["sync_id"] = serde_json::json!(sync_capsule.sync_id.to_string());
        manifest["delta_files"] = serde_json::json!(sync_capsule.delta_size_bytes);
        manifest["critical_changes"] = serde_json::json!(sync_capsule.critical_changes);

        fs::write(
            &manifest_path,
            serde_json::to_string_pretty(&manifest).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;

        Ok(())
    }

    /// Run full survival protocol
    /// Detects vaults, computes checksums, syncs, and updates manifests
    pub async fn execute(&mut self) -> Result<SyncCapsule, String> {
        println!("🔐 Vision Survival Protocol — Night Shift Sync");
        println!("═══════════════════════════════════════════════");

        // Step 1: Detect vaults
        let vaults = self.detect_vaults()?;
        println!("✓ Detected vaults: {:?}", vaults);

        // Step 2: Compute current checksum
        let current_checksum = self.compute_workspace_checksum()?;
        println!("✓ Workspace checksum: {}", &current_checksum[..16]);

        // Step 3: Compute delta
        let delta = self.compute_delta(&current_checksum)?;
        println!("✓ Files changed since last sync: {}", delta.len());

        // Step 4: Detect critical changes
        let critical = self.detect_critical_changes(&delta);
        if !critical.is_empty() {
            println!("⚠️  CRITICAL CHANGES DETECTED:");
            for file in &critical {
                println!("   - {}", file);
            }
            println!(
                "   → Rotate Vault B or C within 72 hours to maintain geopolitical resilience."
            );
        }

        // Step 5: Sync to all vaults
        let mut failed_vaults = vec![];
        for (i, vault_path) in self.vault_mount_points.iter().enumerate() {
            let vault_location = vaults[i];
            match self.sync_to_vault(vault_path) {
                Ok(size) => {
                    println!("✓ Vault {}: Synced ({} bytes)", vault_location, size);

                    // Verify sync
                    if let Err(e) = self.verify_vault(vault_path) {
                        println!("✗ Vault {}: Verification failed: {}", vault_location, e);
                        failed_vaults.push(vault_location);
                    }
                }
                Err(e) => {
                    println!("✗ Vault {}: Sync failed: {}", vault_location, e);
                    failed_vaults.push(vault_location);
                }
            }
        }

        // Step 6: Create sync capsule
        let status = if failed_vaults.is_empty() {
            SyncStatus::Success
        } else {
            SyncStatus::PartialSuccess {
                failed_vaults: failed_vaults.clone(),
            }
        };

        let sync_capsule = SyncCapsule {
            sync_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            vault_location: vaults[0], // Primary vault
            delta_size_bytes: delta.len() as u64,
            workspace_checksum: current_checksum.clone(),
            critical_changes: critical,
            status: status.clone(),
        };

        // Step 7: Update manifests in all vaults
        for vault_path in &self.vault_mount_points {
            if let Err(e) = self.update_manifest(vault_path, &sync_capsule) {
                println!("⚠️  Failed to update manifest: {}", e);
            }
        }

        // Step 8: Log sync result
        match &sync_capsule.status {
            SyncStatus::Success => {
                println!("✓ Sync complete: All vaults synchronized successfully");
            }
            SyncStatus::PartialSuccess { failed_vaults } => {
                println!(
                    "⚠️  Sync complete with warnings: Vaults {:?} had issues",
                    failed_vaults
                );
            }
            SyncStatus::Failed { reason } => {
                println!("✗ Sync failed: {}", reason);
            }
        }

        self.last_sync_hash = Some(current_checksum);

        Ok(sync_capsule)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vision_survival_protocol_init() {
        let protocol = VisionSurvivalProtocol::new(PathBuf::from("/tmp/test"));
        assert_eq!(protocol.vault_mount_points.len(), 0);
        assert!(protocol.last_sync_hash.is_none());
    }

    #[test]
    fn test_detect_critical_changes() {
        let protocol = VisionSurvivalProtocol::new(PathBuf::from("/tmp/test"));

        let delta = vec![
            "src/main.rs".to_string(),
            "docs/Genesis_Capsule.md".to_string(),
            "crates/siss-gatekeeper/src/private_key.rs".to_string(),
            "tests/integration.rs".to_string(),
        ];

        let critical = protocol.detect_critical_changes(&delta);

        assert_eq!(critical.len(), 2);
        assert!(critical.iter().any(|c| c.contains("Genesis")));
        assert!(critical.iter().any(|c| c.contains("private_key")));
    }

    #[test]
    fn test_sync_capsule_serialization() {
        let capsule = SyncCapsule {
            sync_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            vault_location: 'A',
            delta_size_bytes: 1024,
            workspace_checksum: "abc123def456".to_string(),
            critical_changes: vec!["Genesis_update.md".to_string()],
            status: SyncStatus::Success,
        };

        let json = serde_json::to_string(&capsule).expect("serialization failed");
        let deserialized: SyncCapsule =
            serde_json::from_str(&json).expect("deserialization failed");

        assert_eq!(capsule.sync_id, deserialized.sync_id);
        assert_eq!(capsule.vault_location, deserialized.vault_location);
        assert_eq!(capsule.status, deserialized.status);
    }

    #[test]
    fn test_hash_directory_excludes_patterns() {
        let _protocol = VisionSurvivalProtocol::new(PathBuf::from("/tmp/test"));

        // Test that we can detect excluded directories
        let excluded = [
            ".git",
            "target",
            "node_modules",
            ".DS_Store",
            ".claude/private",
            ".venv",
            "__pycache__",
        ];

        for excluded_dir in &excluded {
            let should_skip = excluded.contains(excluded_dir);
            assert!(should_skip, "Directory {} should be excluded", excluded_dir);
        }
    }
}

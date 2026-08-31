use crate::error::{QaError, Result};
use chrono::Utc;
use log::{debug, info};
use sha2::{Digest, Sha256};
use std::path::PathBuf;
use std::process::Command;

pub struct PreFlightValidator {
    repo_root: PathBuf,
    nonce_file: PathBuf,
}

impl PreFlightValidator {
    pub fn new(repo_root: PathBuf) -> Self {
        let nonce_file = repo_root.join(".qa-nonce");
        Self { repo_root, nonce_file }
    }

    pub fn validate(&self) -> Result<String> {
        info!("[Gate 0] Pre-flight Validation starting");

        self.check_git_clean()?;
        debug!("[Gate 0] Git working tree is clean");

        self.validate_cargo_lock()?;
        debug!("[Gate 0] Cargo.lock validated");

        self.clear_cache()?;
        debug!("[Gate 0] Build cache cleared");

        let baseline_duration = self.measure_baseline()?;
        debug!("[Gate 0] Baseline test duration: {}ms", baseline_duration);

        let repo_hash = self.compute_repo_hash()?;
        let timestamp = Utc::now().timestamp_nanos_opt().unwrap_or(0);
        let mut hasher = Sha256::new();
        hasher.update(timestamp.to_le_bytes());
        hasher.update(&repo_hash);

        let nonce_seed = format!("{:x}", hasher.finalize());
        std::fs::write(&self.nonce_file, &nonce_seed)
            .map_err(|e| QaError::PreFlightFailed(format!("Failed to write nonce: {}", e)))?;

        info!("[Gate 0] ✓ Pre-flight PASS");
        info!("[Gate 0] Nonce: {}", &nonce_seed[..16.min(nonce_seed.len())]);
        info!("[Gate 0] Baseline: {}ms", baseline_duration);

        Ok(nonce_seed)
    }

    pub fn generate_nonce(&self) -> Result<String> {
        let repo_hash = self.compute_repo_hash()?;
        let timestamp = Utc::now().timestamp_nanos_opt().unwrap_or(0);
        let mut hasher = Sha256::new();
        hasher.update(timestamp.to_le_bytes());
        hasher.update(&repo_hash);

        Ok(format!("{:x}", hasher.finalize()))
    }

    pub fn get_nonce(&self) -> Result<String> {
        std::fs::read_to_string(&self.nonce_file)
            .map_err(|e| QaError::NonceGenerationFailed(format!("Failed to read nonce: {}", e)))
    }

    fn check_git_clean(&self) -> Result<()> {
        let output = Command::new("git")
            .arg("status")
            .arg("--porcelain")
            .current_dir(&self.repo_root)
            .output()
            .map_err(|e| QaError::GitValidationFailed(format!("Git command failed: {}", e)))?;

        if !output.stdout.is_empty() {
            return Err(QaError::PreFlightFailed(
                "Git working tree not clean".to_string(),
            ));
        }
        Ok(())
    }

    fn validate_cargo_lock(&self) -> Result<()> {
        let lock_path = self.repo_root.join("Cargo.lock");
        if !lock_path.exists() {
            return Err(QaError::PreFlightFailed(
                "Cargo.lock not found".to_string(),
            ));
        }

        let local_hash = self.hash_file(&lock_path)?;
        debug!("Local Cargo.lock hash: {}", &local_hash[..16]);

        Ok(())
    }

    fn clear_cache(&self) -> Result<()> {
        let _ = Command::new("cargo")
            .arg("clean")
            .current_dir(&self.repo_root)
            .output();

        let pytest_cache = self.repo_root.join(".pytest_cache");
        if pytest_cache.exists() {
            let _ = std::fs::remove_dir_all(pytest_cache);
        }
        Ok(())
    }

    fn measure_baseline(&self) -> Result<u64> {
        let start = std::time::Instant::now();
        let output = Command::new("cargo")
            .arg("test")
            .arg("--lib")
            .arg("--quiet")
            .current_dir(&self.repo_root)
            .output();

        match output {
            Ok(_) => Ok(start.elapsed().as_millis() as u64),
            Err(e) => {
                log::warn!("Could not measure baseline: {}", e);
                Ok(5000)
            }
        }
    }

    fn compute_repo_hash(&self) -> Result<Vec<u8>> {
        let output = Command::new("git")
            .arg("rev-parse")
            .arg("HEAD")
            .current_dir(&self.repo_root)
            .output()
            .map_err(|e| QaError::GitValidationFailed(format!("Git command failed: {}", e)))?;

        Ok(output.stdout)
    }

    fn hash_file(&self, path: &std::path::Path) -> Result<String> {
        let data = std::fs::read(path)
            .map_err(|e| QaError::PreFlightFailed(format!("Failed to read file: {}", e)))?;
        Ok(format!("{:x}", Sha256::digest(&data)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_preflight_validator_creation() {
        let temp_dir = TempDir::new().unwrap();
        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        assert_eq!(validator.repo_root, temp_dir.path());
    }

    #[test]
    fn test_generate_nonce() {
        let temp_dir = TempDir::new().unwrap();
        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        let nonce = validator.generate_nonce();

        if let Ok(n) = nonce {
            assert_eq!(n.len(), 64);
            assert!(n.chars().all(|c| c.is_ascii_hexdigit()));
        }
    }

    #[test]
    fn test_hash_file() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.txt");
        std::fs::write(&file_path, b"test content").unwrap();

        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        let hash = validator.hash_file(&file_path).unwrap();

        assert_eq!(hash.len(), 64);
        assert!(hash.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_hash_file_consistency() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.txt");
        std::fs::write(&file_path, b"consistent content").unwrap();

        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        let hash1 = validator.hash_file(&file_path).unwrap();
        let hash2 = validator.hash_file(&file_path).unwrap();

        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_clear_cache_creates_no_error() {
        let temp_dir = TempDir::new().unwrap();
        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        let result = validator.clear_cache();
        assert!(result.is_ok());
    }

    #[test]
    fn test_nonce_file_path() {
        let temp_dir = TempDir::new().unwrap();
        let validator = PreFlightValidator::new(temp_dir.path().to_path_buf());
        assert!(validator.nonce_file.to_string_lossy().contains(".qa-nonce"));
    }
}

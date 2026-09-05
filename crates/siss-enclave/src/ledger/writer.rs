use super::OperatorAuditLog;
use std::path::Path;
use std::sync::Arc;
use tokio::fs::File;
use tokio::io::AsyncWriteExt;
use tokio::sync::Mutex;

#[derive(Clone)]
pub struct PolicyLedgerWriter {
    file: Arc<Mutex<File>>,
}

impl PolicyLedgerWriter {
    /// Create a new PolicyLedgerWriter, creating the ledger file if it doesn't exist.
    /// Returns error if the path is invalid or file cannot be created.
    pub async fn new(path: &Path) -> Result<Self, String> {
        let file = tokio::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .await
            .map_err(|e| e.to_string())?;

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let permissions = std::fs::Permissions::from_mode(0o700);
            tokio::fs::set_permissions(path, permissions)
                .await
                .map_err(|e| e.to_string())?;
        }

        Ok(Self {
            file: Arc::new(Mutex::new(file)),
        })
    }

    /// Append an entry to the ledger as a JSON line.
    /// This is non-blocking and safe for concurrent calls via tokio::spawn.
    pub async fn append(&self, entry: &OperatorAuditLog) -> Result<(), String> {
        let json = serde_json::to_string(entry).map_err(|e| e.to_string())?;
        let mut file = self.file.lock().await;
        file.write_all(json.as_bytes())
            .await
            .map_err(|e| e.to_string())?;
        file.write_all(b"\n").await.map_err(|e| e.to_string())?;
        file.flush().await.map_err(|e| e.to_string())?;
        Ok(())
    }
}

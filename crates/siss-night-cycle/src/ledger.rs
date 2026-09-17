use chrono::Utc;
use serde_json::json;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

fn exec_log_path() -> PathBuf {
    std::env::var("SISS_WORKSPACE")
        .map(|w| PathBuf::from(w).join("EXEC_LOG.json"))
        .unwrap_or_else(|_| PathBuf::from("EXEC_LOG.json"))
}

pub fn append_audit(event: &str, msg: &str) -> std::io::Result<()> {
    let path = exec_log_path();

    let log_entry = json!({
        "timestamp": Utc::now().to_rfc3339(),
        "event": event,
        "message": msg,
        "source": "siss-night-cycle"
    });

    let line = format!("{}\n", log_entry);
    fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?
        .write_all(line.as_bytes())?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_append_audit() {
        let result = append_audit("test_event", "test message");
        assert!(result.is_ok(), "append_audit should succeed");
    }
}

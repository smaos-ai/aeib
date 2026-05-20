use crate::types::ExecutorConfig;
use crate::Result;
use std::path::Path;
use tokio::fs;

/// Load executor configuration from file or use defaults
pub async fn load_config<P: AsRef<Path>>(path: Option<P>) -> Result<ExecutorConfig> {
    if let Some(p) = path {
        let content = fs::read_to_string(p).await?;
        let config = serde_json::from_str(&content)?;
        Ok(config)
    } else {
        Ok(ExecutorConfig::default())
    }
}

/// Save executor configuration to file
pub async fn save_config<P: AsRef<Path>>(
    config: &ExecutorConfig,
    path: P,
) -> Result<()> {
    let content = serde_json::to_string_pretty(config)?;
    fs::write(path, content).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_default_config() {
        let config = ExecutorConfig::default();
        assert_eq!(config.max_agents, 5);
        assert_eq!(config.lock_timeout_secs, 30);
    }
}

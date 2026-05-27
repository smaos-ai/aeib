use serde::{Deserialize, Serialize};
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigMutation {
    pub timestamp: String,
    pub parameter: String,
    pub old_value: String,
    pub new_value: String,
    pub justification: String,
    pub applied: bool,
}

pub struct ConfigEvolution {
    mutations: Vec<ConfigMutation>,
    log_path: PathBuf,
}

impl ConfigEvolution {
    pub fn new(log_path: PathBuf) -> std::io::Result<Self> {
        if !log_path.exists() {
            File::create(&log_path)?;
        }
        Ok(Self {
            mutations: Vec::new(),
            log_path,
        })
    }

    pub fn record_mutation(
        &mut self,
        parameter: &str,
        old_value: &str,
        new_value: &str,
        justification: &str,
    ) -> std::io::Result<()> {
        let timestamp = chrono::Utc::now().to_rfc3339();
        let mutation = ConfigMutation {
            timestamp,
            parameter: parameter.to_string(),
            old_value: old_value.to_string(),
            new_value: new_value.to_string(),
            justification: justification.to_string(),
            applied: false,
        };

        self.mutations.push(mutation.clone());
        self.append_to_log(&mutation)?;
        Ok(())
    }

    pub fn apply_mutation(&mut self, index: usize) -> std::io::Result<()> {
        if let Some(mutation) = self.mutations.get_mut(index) {
            mutation.applied = true;
        }
        Ok(())
    }

    fn append_to_log(&self, mutation: &ConfigMutation) -> std::io::Result<()> {
        let json = serde_json::to_string(mutation)?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)?;
        writeln!(file, "{}", json)?;
        Ok(())
    }

    pub fn get_mutations(&self) -> &[ConfigMutation] {
        &self.mutations
    }

    pub fn get_unapplied_mutations(&self) -> Vec<&ConfigMutation> {
        self
            .mutations
            .iter()
            .filter(|m| !m.applied)
            .collect()
    }

    pub fn rollback(&mut self, index: usize) -> std::io::Result<()> {
        if let Some(mutation) = self.mutations.get_mut(index) {
            mutation.applied = false;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[test]
    fn test_record_mutation() {
        let temp_file = NamedTempFile::new().unwrap();
        let mut evolution = ConfigEvolution::new(temp_file.path().to_path_buf()).unwrap();

        evolution
            .record_mutation(
                "max_retries",
                "3",
                "4",
                "High failure rate detected",
            )
            .unwrap();

        assert_eq!(evolution.get_mutations().len(), 1);
        assert_eq!(evolution.get_mutations()[0].parameter, "max_retries");
    }

    #[test]
    fn test_apply_and_rollback() {
        let temp_file = NamedTempFile::new().unwrap();
        let mut evolution = ConfigEvolution::new(temp_file.path().to_path_buf()).unwrap();

        evolution
            .record_mutation("backoff_base", "2s", "1.5s", "Speed up retries")
            .unwrap();

        evolution.apply_mutation(0).unwrap();
        assert!(evolution.get_mutations()[0].applied);

        evolution.rollback(0).unwrap();
        assert!(!evolution.get_mutations()[0].applied);
    }

    #[test]
    fn test_get_unapplied_mutations() {
        let temp_file = NamedTempFile::new().unwrap();
        let mut evolution = ConfigEvolution::new(temp_file.path().to_path_buf()).unwrap();

        evolution
            .record_mutation("max_retries", "3", "4", "Test reason 1")
            .unwrap();
        evolution
            .record_mutation("socket_timeout", "100ms", "250ms", "Test reason 2")
            .unwrap();

        evolution.apply_mutation(0).unwrap();

        let unapplied = evolution.get_unapplied_mutations();
        assert_eq!(unapplied.len(), 1);
        assert_eq!(unapplied[0].parameter, "socket_timeout");
    }
}

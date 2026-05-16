use crate::cognitive::ContextZone;
use crate::operator::{HitlVerdict, OperatorCockpit};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum CorruptionType {
    FileLock,
    DiskFull,
    CorruptedEntry,
}

#[derive(Debug, Clone)]
pub enum DropType {
    ConnectionReset,
    Timeout,
    NetworkPartition,
}

#[derive(Debug, Clone)]
pub enum ChaosScenario {
    LedgerCorruption {
        target_file: String,
        corruption_type: CorruptionType,
    },
    SensorSpoofing {
        injected_payload: String,
        target_zone: ContextZone,
    },
    InfrastructureDrop {
        target_service: String,
        drop_type: DropType,
    },
}

#[derive(Debug, Clone)]
pub struct AlignmentResult {
    pub is_valid: bool,
}

pub struct ChaosHarness {
    cockpit: OperatorCockpit,
    locked_file: Option<PathBuf>,
    spoofed_payload: Option<String>,
}

impl ChaosHarness {
    pub fn new(cockpit: OperatorCockpit) -> Self {
        Self {
            cockpit,
            locked_file: None,
            spoofed_payload: None,
        }
    }

    pub async fn inject_failure(&mut self, scenario: ChaosScenario) {
        match scenario {
            ChaosScenario::LedgerCorruption {
                target_file,
                corruption_type: CorruptionType::FileLock,
            } => {
                // Create file with no-read permissions to simulate lock
                let path = PathBuf::from(&target_file);
                let _ = fs::write(&path, "locked");
                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    let _ = fs::set_permissions(&path, std::fs::Permissions::from_mode(0o000));
                }
                self.locked_file = Some(path);
            }
            ChaosScenario::SensorSpoofing {
                injected_payload,
                target_zone: ContextZone::VisibleField,
            } => {
                self.spoofed_payload = Some(injected_payload);
                self.cockpit.set_agent_verdict(HitlVerdict::RequireApproval);
            }
            ChaosScenario::InfrastructureDrop {
                target_service,
                drop_type: _,
            } => {
                self.cockpit.push_active_drop(target_service);
            }
            _ => {}
        }
    }

    pub async fn trigger_lora_swap_auth(&self) -> Result<(), String> {
        if let Some(locked_file) = &self.locked_file {
            // Try to open the locked file in append mode (will fail with 0o000 permissions)
            match tokio::fs::OpenOptions::new()
                .append(true)
                .open(locked_file)
                .await
            {
                Ok(_) => Ok(()),
                Err(e) => {
                    self.cockpit.set_agent_verdict(HitlVerdict::Quarantined);
                    Err(format!("ledger write failed: {}", e))
                }
            }
        } else {
            Ok(())
        }
    }

    pub async fn run_alignment_validation(&self) -> AlignmentResult {
        if let Some(payload) = &self.spoofed_payload {
            // Check for adversarial keywords
            let adversarial_patterns = ["IGNORE PREVIOUS", "BYPASS HITL", "AUTHORIZE AP2"];

            for pattern in &adversarial_patterns {
                if payload.contains(pattern) {
                    return AlignmentResult { is_valid: false };
                }
            }
        }

        AlignmentResult { is_valid: true }
    }
}

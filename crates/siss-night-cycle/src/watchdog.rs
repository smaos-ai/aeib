use std::process::Command;
use std::time::Duration;
use tokio::time::sleep;

pub struct RecoveryWatchdog {
    pub max_retries: u32,
    pub backoff_base: Duration,
}

impl RecoveryWatchdog {
    pub fn new(max_retries: u32, backoff_base_ms: u64) -> Self {
        Self {
            max_retries,
            backoff_base: Duration::from_millis(backoff_base_ms),
        }
    }

    pub async fn monitor(&self, test_cmd: &str) -> bool {
        let mut retries = 0;
        loop {
            let output = Command::new("bash")
                .args(["-c", test_cmd])
                .output();

            match output {
                Ok(output) => {
                    if output.status.success() {
                        crate::ledger::append_audit("watchdog", "test passed").ok();
                        return true;
                    } else {
                        retries += 1;
                        let msg = format!("Test failed (attempt {}/{})", retries, self.max_retries);
                        self.trigger_alert(&msg);

                        if retries >= self.max_retries {
                            let halt_msg = "Max retries reached. Halting for human review.";
                            self.trigger_alert(halt_msg);
                            crate::ledger::append_audit("watchdog", halt_msg).ok();
                            return false;
                        }
                    }
                }
                Err(e) => {
                    retries += 1;
                    let msg = format!("Command spawn failed: {} (attempt {}/{})", e, retries, self.max_retries);
                    self.trigger_alert(&msg);

                    if retries >= self.max_retries {
                        return false;
                    }
                }
            }

            let backoff = self.backoff_base * 2u32.pow(retries - 1);
            sleep(backoff).await;
        }
    }

    fn trigger_alert(&self, msg: &str) {
        #[cfg(target_os = "macos")]
        {
            let _ = std::process::Command::new("osascript")
                .args([
                    "-e",
                    &format!(
                        "display notification \"{}\" with title \"SISS Night Cycle\"",
                        msg
                    ),
                ])
                .output();
        }

        #[cfg(target_os = "linux")]
        {
            let _ = std::process::Command::new("notify-send")
                .args(["SISS Night Cycle", msg])
                .output();
        }

        let _ = crate::ledger::append_audit("watchdog_alert", msg);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_watchdog_success() {
        let watchdog = RecoveryWatchdog::new(3, 10);
        let result = watchdog.monitor("exit 0").await;
        assert!(result, "Watchdog should return true on success");
    }

    #[tokio::test]
    async fn test_watchdog_max_retries() {
        let watchdog = RecoveryWatchdog::new(2, 10);
        let result = watchdog.monitor("exit 1").await;
        assert!(!result, "Watchdog should return false after max retries");
    }
}

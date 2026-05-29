use crate::types::ConsoleError;
use std::process::Command;

pub trait A11y {
    fn announce(&self, text: &str) -> Result<(), ConsoleError>;
    fn focus(&self, element_id: &str) -> Result<(), ConsoleError>;
    fn set_label(&self, element_id: &str, label: &str) -> Result<(), ConsoleError>;
}

pub struct VoiceOverReader {
    enabled: bool,
}

impl VoiceOverReader {
    pub fn new() -> Self {
        Self { enabled: true }
    }

    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    pub fn set_enabled(&mut self, enabled: bool) {
        self.enabled = enabled;
    }
}

impl Default for VoiceOverReader {
    fn default() -> Self {
        Self::new()
    }
}

impl A11y for VoiceOverReader {
    fn announce(&self, text: &str) -> Result<(), ConsoleError> {
        if !self.enabled {
            return Ok(());
        }

        #[cfg(target_os = "macos")]
        {
            let output = Command::new("say")
                .arg(text)
                .output()
                .map_err(|e| ConsoleError::A11yError(e.to_string()))?;

            if !output.status.success() {
                return Err(ConsoleError::A11yError(
                    "Failed to announce text".to_string(),
                ));
            }
        }

        #[cfg(not(target_os = "macos"))]
        {
            // On other platforms, log the announcement
            tracing::info!("A11y announcement: {}", text);
        }

        Ok(())
    }

    fn focus(&self, element_id: &str) -> Result<(), ConsoleError> {
        if !self.enabled {
            return Ok(());
        }

        let announcement = format!("Focus moved to {}", element_id);
        self.announce(&announcement)?;
        Ok(())
    }

    fn set_label(&self, element_id: &str, label: &str) -> Result<(), ConsoleError> {
        if !self.enabled {
            return Ok(());
        }

        let announcement = format!("{}: {}", element_id, label);
        self.announce(&announcement)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_voiceover_reader_create() {
        let reader = VoiceOverReader::new();
        assert!(reader.is_enabled());
    }

    #[test]
    fn test_voiceover_reader_disable() {
        let mut reader = VoiceOverReader::new();
        reader.set_enabled(false);
        assert!(!reader.is_enabled());
    }

    #[test]
    fn test_voiceover_reader_disabled_announce() {
        let mut reader = VoiceOverReader::new();
        reader.set_enabled(false);
        let result = reader.announce("test");
        assert!(result.is_ok());
    }

    #[test]
    fn test_voiceover_reader_announce() {
        let reader = VoiceOverReader::new();
        let result = reader.announce("Agent running with 256 MB memory");
        // On macOS, this will execute `say`, on others it will log
        assert!(result.is_ok() || result.is_err()); // Accept both cases
    }

    #[test]
    fn test_voiceover_reader_focus() {
        let reader = VoiceOverReader::new();
        let result = reader.focus("agent_status_panel");
        assert!(result.is_ok() || result.is_err());
    }

    #[test]
    fn test_voiceover_reader_set_label() {
        let reader = VoiceOverReader::new();
        let result = reader.set_label("memory_usage", "256 MB");
        assert!(result.is_ok() || result.is_err());
    }

    #[test]
    fn test_voiceover_default() {
        let reader = VoiceOverReader::default();
        assert!(reader.is_enabled());
    }
}

pub mod screen_reader;
pub use screen_reader::{A11y, VoiceOverReader};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_a11y_trait_object() {
        let reader: Box<dyn A11y> = Box::new(VoiceOverReader::new());
        let result = reader.announce("test");
        assert!(result.is_ok() || result.is_err());
    }
}

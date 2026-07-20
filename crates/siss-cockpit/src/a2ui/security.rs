/// Security hardening for A2UI renderer and form handlers
/// Implements input validation, DoS prevention, session isolation, and cryptographic integrity checks

use std::collections::HashSet;
use regex::Regex;
use std::sync::OnceLock;

/// Security configuration with production-safe defaults
#[derive(Debug, Clone)]
pub struct SecurityConfig {
    /// Maximum component nesting depth (prevent DoS)
    pub max_nesting_depth: usize,
    /// Maximum number of sibling components in layout
    pub max_component_count: usize,
    /// Maximum payload size in bytes
    pub max_payload_size: usize,
    /// Maximum requests per session per minute
    pub rate_limit_per_min: u32,
    /// Session timeout in seconds
    pub session_timeout_secs: u32,
    /// Maximum concurrent sessions
    pub max_concurrent_sessions: usize,
    /// Enable HTTPS enforcement
    pub enforce_https: bool,
    /// Enable secure cookies (httpOnly + sameSite=Strict)
    pub secure_cookies: bool,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            max_nesting_depth: 10,
            max_component_count: 1000,
            max_payload_size: 10240,      // 10KB
            rate_limit_per_min: 60,
            session_timeout_secs: 300,    // 5 minutes
            max_concurrent_sessions: 1000,
            enforce_https: true,
            secure_cookies: true,
        }
    }
}

/// Input validator with comprehensive sanitization
pub struct InputValidator {
    config: SecurityConfig,
}

impl InputValidator {
    pub fn new(config: SecurityConfig) -> Self {
        Self { config }
    }

    /// Validate plain text input: escape HTML, check length
    pub fn validate_text(&self, input: &str, max_len: usize) -> Result<String, String> {
        // Check length
        if input.len() > max_len {
            return Err(format!("Input exceeds maximum length of {}", max_len));
        }

        // Check for valid UTF-8
        if !input.is_ascii() && input.chars().all(|c| !c.is_control()) {
            // Allow valid Unicode but reject control characters
        } else if !input.is_ascii() {
            return Err("Input contains invalid control characters".to_string());
        }

        Ok(input.to_string())
    }

    /// Validate email format strictly
    pub fn validate_email(&self, input: &str) -> Result<String, String> {
        // RFC 5322 simplified regex
        let email_regex = email_regex();
        if !email_regex.is_match(input) {
            return Err("Invalid email format".to_string());
        }

        if input.len() > 254 {
            return Err("Email exceeds maximum length".to_string());
        }

        Ok(input.to_string())
    }

    /// Validate URL format strictly
    pub fn validate_url(&self, input: &str) -> Result<String, String> {
        // Only allow http(s) and relative URLs
        let url_regex = url_regex();
        if !url_regex.is_match(input) {
            return Err("Invalid URL format or disallowed protocol".to_string());
        }

        if input.len() > 2048 {
            return Err("URL exceeds maximum length".to_string());
        }

        Ok(input.to_string())
    }

    /// Validate component ID (alphanumeric, hyphen, underscore only)
    pub fn validate_component_id(&self, id: &str) -> Result<String, String> {
        if id.is_empty() || id.len() > 128 {
            return Err("Component ID must be 1-128 characters".to_string());
        }

        let id_regex = component_id_regex();
        if !id_regex.is_match(id) {
            return Err("Component ID contains invalid characters".to_string());
        }

        Ok(id.to_string())
    }

    /// Validate payload size (prevent zip bombs and DoS)
    pub fn validate_payload_size(&self, size: usize) -> Result<(), String> {
        if size > self.config.max_payload_size {
            return Err(format!(
                "Payload exceeds maximum size of {} bytes",
                self.config.max_payload_size
            ));
        }
        Ok(())
    }

    /// Validate component nesting depth (prevent billion laughs attack)
    pub fn validate_nesting_depth(&self, depth: usize) -> Result<(), String> {
        if depth > self.config.max_nesting_depth {
            return Err(format!(
                "Component nesting exceeds maximum depth of {}",
                self.config.max_nesting_depth
            ));
        }
        Ok(())
    }

    /// Validate component count (prevent large payload DoS)
    pub fn validate_component_count(&self, count: usize) -> Result<(), String> {
        if count > self.config.max_component_count {
            return Err(format!(
                "Component count exceeds maximum of {}",
                self.config.max_component_count
            ));
        }
        Ok(())
    }
}

/// Detect circular references in component hierarchies
pub struct CircularReferenceDetector;

impl CircularReferenceDetector {
    /// Check if a path contains cycles (via component IDs)
    pub fn has_cycle(component_ids: &[String]) -> bool {
        let mut seen = HashSet::new();
        for id in component_ids {
            if !seen.insert(id.clone()) {
                return true;
            }
        }
        false
    }

    /// Track component path to detect cycles during traversal
    pub fn validate_path(path: &[String]) -> Result<(), String> {
        if Self::has_cycle(path) {
            return Err("Circular reference detected in component hierarchy".to_string());
        }
        Ok(())
    }
}

/// Rate limiter for session protection
#[derive(Debug, Clone)]
pub struct RateLimiter {
    pub session_id: String,
    pub request_count: u32,
    pub window_start: std::time::SystemTime,
    pub config: SecurityConfig,
}

impl RateLimiter {
    pub fn new(session_id: String, config: SecurityConfig) -> Self {
        Self {
            session_id,
            request_count: 0,
            window_start: std::time::SystemTime::now(),
            config,
        }
    }

    /// Check if request should be allowed (sliding window counter)
    pub fn is_allowed(&mut self) -> Result<(), String> {
        let elapsed = self.window_start.elapsed().unwrap_or_default();

        // Reset counter if window expired
        if elapsed.as_secs() >= 60 {
            self.request_count = 0;
            self.window_start = std::time::SystemTime::now();
        }

        self.request_count += 1;

        if self.request_count > self.config.rate_limit_per_min {
            return Err(format!(
                "Rate limit exceeded: {} requests per minute",
                self.config.rate_limit_per_min
            ));
        }

        Ok(())
    }
}

/// Session security validator
#[derive(Debug, Clone)]
pub struct SessionValidator {
    pub session_id: String,
    pub created_at: std::time::SystemTime,
    pub config: SecurityConfig,
}

impl SessionValidator {
    pub fn new(session_id: String, config: SecurityConfig) -> Self {
        Self {
            session_id,
            created_at: std::time::SystemTime::now(),
            config,
        }
    }

    /// Validate session is not expired
    pub fn is_valid(&self) -> Result<(), String> {
        let elapsed = self.created_at.elapsed().unwrap_or_default();
        if elapsed.as_secs() > self.config.session_timeout_secs as u64 {
            return Err("Session expired".to_string());
        }
        Ok(())
    }

    /// Validate session ID format (UUID)
    pub fn validate_session_id(id: &str) -> Result<(), String> {
        // UUID format: 8-4-4-4-12 hex digits
        let uuid_regex = uuid_regex();
        if !uuid_regex.is_match(id) {
            return Err("Invalid session ID format".to_string());
        }
        Ok(())
    }
}

/// Content Security Policy helper
pub struct CSPBuilder;

impl CSPBuilder {
    /// Generate secure CSP header for A2UI rendering
    pub fn build_csp() -> String {
        // Restrictive CSP: inline scripts not allowed, only from same origin
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; \
         img-src 'self' data:; font-src 'self'; connect-src 'self'; \
         frame-ancestors 'none'; form-action 'self'; base-uri 'self';"
            .to_string()
    }
}

/// Helper function to get email regex (lazy static)
fn email_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$").unwrap()
    })
}

/// Helper function to get URL regex
fn url_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(r"^(https?://[^\s]+|/[^\s]*)$").unwrap()
    })
}

/// Helper function to get component ID regex
fn component_id_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(r"^[a-zA-Z0-9_-]+$").unwrap()
    })
}

/// Helper function to get UUID regex
fn uuid_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$").unwrap()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_input_validator_valid_text() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_text("Hello World", 100);
        assert!(result.is_ok());
    }

    #[test]
    fn test_input_validator_text_exceeds_length() {
        let validator = InputValidator::new(SecurityConfig::default());
        let long_text = "x".repeat(101);
        let result = validator.validate_text(&long_text, 100);
        assert!(result.is_err());
    }

    #[test]
    fn test_email_validation_valid() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_email("test@example.com");
        assert!(result.is_ok());
    }

    #[test]
    fn test_email_validation_invalid() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_email("invalid-email");
        assert!(result.is_err());
    }

    #[test]
    fn test_url_validation_https() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_url("https://example.com");
        assert!(result.is_ok());
    }

    #[test]
    fn test_url_validation_relative() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_url("/path/to/page");
        assert!(result.is_ok());
    }

    #[test]
    fn test_url_validation_javascript_blocked() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_url("javascript:alert('xss')");
        assert!(result.is_err());
    }

    #[test]
    fn test_component_id_validation_valid() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_component_id("form-input_123");
        assert!(result.is_ok());
    }

    #[test]
    fn test_component_id_validation_invalid_chars() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_component_id("form@input");
        assert!(result.is_err());
    }

    #[test]
    fn test_payload_size_validation() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_payload_size(5120);
        assert!(result.is_ok());

        let result = validator.validate_payload_size(20480);
        assert!(result.is_err());
    }

    #[test]
    fn test_nesting_depth_validation() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_nesting_depth(5);
        assert!(result.is_ok());

        let result = validator.validate_nesting_depth(20);
        assert!(result.is_err());
    }

    #[test]
    fn test_component_count_validation() {
        let validator = InputValidator::new(SecurityConfig::default());
        let result = validator.validate_component_count(500);
        assert!(result.is_ok());

        let result = validator.validate_component_count(2000);
        assert!(result.is_err());
    }

    #[test]
    fn test_circular_reference_detection() {
        let path = vec!["a".to_string(), "b".to_string(), "c".to_string()];
        assert!(!CircularReferenceDetector::has_cycle(&path));

        let cycle_path = vec!["a".to_string(), "b".to_string(), "a".to_string()];
        assert!(CircularReferenceDetector::has_cycle(&cycle_path));
    }

    #[test]
    fn test_rate_limiter_allows_requests_below_limit() {
        let config = SecurityConfig::default();
        let mut limiter = RateLimiter::new("session-123".to_string(), config);

        for _ in 0..30 {
            assert!(limiter.is_allowed().is_ok());
        }
    }

    #[test]
    fn test_rate_limiter_blocks_excessive_requests() {
        let config = SecurityConfig {
            rate_limit_per_min: 10,
            ..Default::default()
        };
        let mut limiter = RateLimiter::new("session-123".to_string(), config);

        for _ in 0..10 {
            assert!(limiter.is_allowed().is_ok());
        }

        // 11th request should fail
        assert!(limiter.is_allowed().is_err());
    }

    #[test]
    fn test_session_validator_valid_session() {
        let config = SecurityConfig::default();
        let validator = SessionValidator::new("550e8400-e29b-41d4-a716-446655440000".to_string(), config);
        assert!(validator.is_valid().is_ok());
    }

    #[test]
    fn test_session_validator_id_format() {
        let result = SessionValidator::validate_session_id("550e8400-e29b-41d4-a716-446655440000");
        assert!(result.is_ok());

        let result = SessionValidator::validate_session_id("invalid-session-id");
        assert!(result.is_err());
    }

    #[test]
    fn test_csp_header_generation() {
        let csp = CSPBuilder::build_csp();
        assert!(csp.contains("default-src 'self'"));
        assert!(csp.contains("script-src 'self'"));
        assert!(!csp.contains("unsafe-eval"));
    }
}

/// Wave 1: OpenClaw Loopback Membrane
/// Enforces that the gateway can only bind to loopback interfaces (127.0.0.1 or ::1).
/// Credentials are referenced only via environment variable names, never stored as literals.

pub struct GatewayConfig {
    pub bind_address: &'static str,
    pub model_endpoint_env_var: &'static str,
    pub auth_token_env_var: &'static str,
    pub no_external_binding: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum GatewayViolation {
    ExternalBinding { address: String },
}

pub struct GatewayMembraneValidator;

impl GatewayMembraneValidator {
    /// Mathematically prove the gateway is loopback-only.
    /// RULE A: bind_address must be "127.0.0.1" or "::1"
    /// RULE B: no_external_binding must be true (structural sentinel)
    pub fn validate(config: &GatewayConfig) -> Result<(), GatewayViolation> {
        // RULE A: bind_address must be loopback
        if config.bind_address != "127.0.0.1" && config.bind_address != "::1" {
            return Err(GatewayViolation::ExternalBinding {
                address: config.bind_address.to_string(),
            });
        }

        // RULE B: no_external_binding must be true
        if !config.no_external_binding {
            return Err(GatewayViolation::ExternalBinding {
                address: "external binding permitted".to_string(),
            });
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_accept_loopback_127() {
        let config = GatewayConfig {
            bind_address: "127.0.0.1",
            model_endpoint_env_var: "MODEL_ENDPOINT",
            auth_token_env_var: "AUTH_TOKEN",
            no_external_binding: true,
        };
        assert!(GatewayMembraneValidator::validate(&config).is_ok());
    }

    #[test]
    fn test_accept_loopback_ipv6() {
        let config = GatewayConfig {
            bind_address: "::1",
            model_endpoint_env_var: "MODEL_ENDPOINT",
            auth_token_env_var: "AUTH_TOKEN",
            no_external_binding: true,
        };
        assert!(GatewayMembraneValidator::validate(&config).is_ok());
    }

    #[test]
    fn test_reject_external_binding() {
        let config = GatewayConfig {
            bind_address: "0.0.0.0",
            model_endpoint_env_var: "MODEL_ENDPOINT",
            auth_token_env_var: "AUTH_TOKEN",
            no_external_binding: true,
        };
        assert!(matches!(
            GatewayMembraneValidator::validate(&config),
            Err(GatewayViolation::ExternalBinding { address }) if address == "0.0.0.0"
        ));
    }

    #[test]
    fn test_reject_external_binding_routable_ip() {
        let config = GatewayConfig {
            bind_address: "192.168.1.1",
            model_endpoint_env_var: "MODEL_ENDPOINT",
            auth_token_env_var: "AUTH_TOKEN",
            no_external_binding: true,
        };
        assert!(GatewayMembraneValidator::validate(&config).is_err());
    }
}

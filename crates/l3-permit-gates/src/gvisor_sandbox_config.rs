use serde::{Deserialize, Serialize};

/// gVisor sandbox configuration for untrusted tool execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GvisorConfig {
    pub enabled: bool,
    pub runsc_binary_path: String,
    pub runtime_name: String,
    pub network_mode: NetworkMode,
    pub resource_limits: ResourceLimits,
    pub security_flags: Vec<String>,
    pub mounts: Vec<GvisorMount>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum NetworkMode {
    /// Isolated network namespace (no external access)
    Isolated,
    /// Sandbox network (loopback only)
    Loopback,
    /// Bridged to host (restricted egress)
    BridgeRestricted,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceLimits {
    pub memory_limit_mb: u32,
    pub cpu_limit_millicores: u32,
    pub file_descriptor_limit: u32,
    pub process_limit: u32,
    pub max_open_files: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GvisorMount {
    pub container_path: String,
    pub host_path: Option<String>,
    pub read_only: bool,
}

impl GvisorConfig {
    /// Default configuration for SMAOS tool sandboxing
    pub fn default_config() -> Self {
        Self {
            enabled: true,
            runsc_binary_path: "/usr/bin/runsc".to_string(),
            runtime_name: "runc".to_string(),
            network_mode: NetworkMode::Isolated,
            resource_limits: ResourceLimits {
                memory_limit_mb: 512,
                cpu_limit_millicores: 1000,
                file_descriptor_limit: 1024,
                process_limit: 100,
                max_open_files: 256,
            },
            security_flags: vec![
                "--network=host".to_string(),
                "--seccomp=unconfined".to_string(),
            ],
            mounts: vec![
                GvisorMount {
                    container_path: "/tmp".to_string(),
                    host_path: None,
                    read_only: false,
                },
                GvisorMount {
                    container_path: "/var/tmp".to_string(),
                    host_path: None,
                    read_only: false,
                },
            ],
        }
    }

    /// Strict configuration for high-risk tools (credit scoring, student records)
    pub fn strict_config() -> Self {
        let mut cfg = Self::default_config();
        cfg.network_mode = NetworkMode::Loopback;
        cfg.resource_limits.memory_limit_mb = 256;
        cfg.resource_limits.cpu_limit_millicores = 500;
        cfg.security_flags.push("--seccomp=/etc/seccomp/default.json".to_string());
        cfg
    }

    /// Permissive configuration for low-risk tools (read-only document analysis)
    pub fn permissive_config() -> Self {
        let mut cfg = Self::default_config();
        cfg.network_mode = NetworkMode::BridgeRestricted;
        cfg.resource_limits.memory_limit_mb = 1024;
        cfg.resource_limits.cpu_limit_millicores = 2000;
        cfg
    }

    /// Generate Docker Compose service definition for sandbox
    pub fn to_docker_compose_service(&self) -> String {
        format!(
            r#"
  tool-sandbox:
    image: gvisor/runsc:latest
    runtime: runsc
    networks:
      - isolated
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    mem_limit: {}m
    cpus: {}
    environment:
      - GVISOR_ENABLE_KVMMEM=true
      - GVISOR_BLOCK_PROCS=true
    tmpfs:
      - /tmp
      - /var/tmp
"#,
            self.resource_limits.memory_limit_mb,
            self.resource_limits.cpu_limit_millicores as f64 / 1000.0
        )
    }

    /// Validate configuration for consistency
    pub fn validate(&self) -> Result<(), String> {
        if self.resource_limits.memory_limit_mb < 128 {
            return Err("Memory limit too low (min 128MB)".to_string());
        }
        if self.resource_limits.cpu_limit_millicores < 100 {
            return Err("CPU limit too low (min 100m)".to_string());
        }
        if self.resource_limits.file_descriptor_limit < 256 {
            return Err("FD limit too low (min 256)".to_string());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let cfg = GvisorConfig::default_config();
        assert!(cfg.enabled);
        assert_eq!(cfg.resource_limits.memory_limit_mb, 512);
    }

    #[test]
    fn test_strict_config_has_lower_resources() {
        let strict = GvisorConfig::strict_config();
        let default = GvisorConfig::default_config();
        assert!(strict.resource_limits.memory_limit_mb < default.resource_limits.memory_limit_mb);
    }

    #[test]
    fn test_permissive_config_has_higher_resources() {
        let permissive = GvisorConfig::permissive_config();
        let default = GvisorConfig::default_config();
        assert!(
            permissive.resource_limits.memory_limit_mb > default.resource_limits.memory_limit_mb
        );
    }

    #[test]
    fn test_config_validation_passes() {
        let cfg = GvisorConfig::default_config();
        assert!(cfg.validate().is_ok());
    }

    #[test]
    fn test_config_validation_fails_low_memory() {
        let mut cfg = GvisorConfig::default_config();
        cfg.resource_limits.memory_limit_mb = 64;
        assert!(cfg.validate().is_err());
    }

    #[test]
    fn test_docker_compose_output() {
        let cfg = GvisorConfig::default_config();
        let output = cfg.to_docker_compose_service();
        assert!(output.contains("gvisor/runsc"));
        assert!(output.contains("512"));
    }
}

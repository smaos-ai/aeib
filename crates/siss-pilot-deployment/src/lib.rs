use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;
use uuid::Uuid;

#[cfg(test)]
mod tests;

#[cfg(test)]
mod integration_tests;

/// Pilot customer profile
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CustomerProfile {
    FinTech,
    Biotech,
    Manufacturing,
}

/// Pilot environment configuration per customer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotEnvironment {
    pub id: String,
    pub customer: CustomerProfile,
    pub num_agents: usize,
    pub num_nodes: usize,
    pub test_data_count: usize,
    pub model_name: String,
    pub deployment_region: String,
    pub network_config: NetworkConfig,
    pub created_at: DateTime<Utc>,
}

/// Network configuration for pilot deployment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    pub vpc_cidr: String,
    pub inter_node_bandwidth_gbps: u32,
    pub mtu_bytes: u32,
}

impl Default for NetworkConfig {
    fn default() -> Self {
        Self {
            vpc_cidr: "10.0.0.0/16".to_string(),
            inter_node_bandwidth_gbps: 10,
            mtu_bytes: 9000,
        }
    }
}

impl PilotEnvironment {
    /// Create FinTech pilot environment: 3-node cluster, 10 agents, 1000 trade orders
    pub fn new_fintech() -> Self {
        Self {
            id: format!("fintech-{}", Uuid::new_v4().to_string()[0..8].to_string()),
            customer: CustomerProfile::FinTech,
            num_agents: 10,
            num_nodes: 3,
            test_data_count: 1000,
            model_name: "trade-router-v1".to_string(),
            deployment_region: "us-east-1".to_string(),
            network_config: NetworkConfig::default(),
            created_at: Utc::now(),
        }
    }

    /// Create Biotech pilot environment: 2-node cluster, 20 agents, 500 hypotheses
    pub fn new_biotech() -> Self {
        Self {
            id: format!("biotech-{}", Uuid::new_v4().to_string()[0..8].to_string()),
            customer: CustomerProfile::Biotech,
            num_agents: 20,
            num_nodes: 2,
            test_data_count: 500,
            model_name: "hypothesis-evaluator-v1".to_string(),
            deployment_region: "us-west-2".to_string(),
            network_config: NetworkConfig::default(),
            created_at: Utc::now(),
        }
    }

    /// Create Manufacturing pilot environment: 2-node cluster, 15 agents, 1000 orders
    pub fn new_manufacturing() -> Self {
        Self {
            id: format!("mfg-{}", Uuid::new_v4().to_string()[0..8].to_string()),
            customer: CustomerProfile::Manufacturing,
            num_agents: 15,
            num_nodes: 2,
            test_data_count: 1000,
            model_name: "scheduler-predictor-v1".to_string(),
            deployment_region: "eu-west-1".to_string(),
            network_config: NetworkConfig::default(),
            created_at: Utc::now(),
        }
    }
}

/// Deployment configuration with success metrics per customer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentConfig {
    pub customer: CustomerProfile,
    pub target_max_latency_ms: u32,
    pub veto_latency_ms: u32,
    pub target_uptime_percent: f64,
    pub max_cost_per_unit: f64,
    pub latency_targets: HashMap<String, u32>,
    pub cost_targets: HashMap<String, f64>,
    pub uptime_targets: HashMap<String, f64>,
}

impl DeploymentConfig {
    /// FinTech config: 10x latency vs Kubernetes, <50ms veto latency
    pub fn for_fintech() -> Self {
        let mut latency_targets = HashMap::new();
        latency_targets.insert("fintech_trade_veto".to_string(), 50);
        latency_targets.insert("fintech_trade_routing".to_string(), 100);

        Self {
            customer: CustomerProfile::FinTech,
            target_max_latency_ms: 50,
            veto_latency_ms: 50,
            target_uptime_percent: 99.9,
            max_cost_per_unit: 0.0,
            latency_targets,
            cost_targets: HashMap::new(),
            uptime_targets: HashMap::new(),
        }
    }

    /// Biotech config: Cost <$10/hypothesis vs baseline $50
    pub fn for_biotech() -> Self {
        let mut cost_targets = HashMap::new();
        cost_targets.insert("biotech_hypothesis".to_string(), 10.0);

        Self {
            customer: CustomerProfile::Biotech,
            target_max_latency_ms: 300,
            veto_latency_ms: 300,
            target_uptime_percent: 99.0,
            max_cost_per_unit: 10.0,
            latency_targets: HashMap::new(),
            cost_targets,
            uptime_targets: HashMap::new(),
        }
    }

    /// Manufacturing config: 99.5% uptime, <50ms decision latency
    pub fn for_manufacturing() -> Self {
        let mut latency_targets = HashMap::new();
        latency_targets.insert("manufacturing_decision".to_string(), 50);
        latency_targets.insert("manufacturing_scheduling".to_string(), 200);

        Self {
            customer: CustomerProfile::Manufacturing,
            target_max_latency_ms: 50,
            veto_latency_ms: 200,
            target_uptime_percent: 99.5,
            max_cost_per_unit: 0.0,
            latency_targets,
            cost_targets: HashMap::new(),
            uptime_targets: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationReport {
    pub environment_id: String,
    pub all_checks_passed: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
    pub validated_at: DateTime<Utc>,
}

#[derive(Debug, Error)]
pub enum DeploymentError {
    #[error("Validation failed: {0}")]
    ValidationFailed(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("Deployment failed: {0}")]
    DeploymentFailed(String),
}

/// Validates pilot environments against requirements
pub struct EnvironmentValidator {
    min_agents: HashMap<CustomerProfile, usize>,
    min_test_data: HashMap<CustomerProfile, usize>,
}

impl EnvironmentValidator {
    pub fn new() -> Self {
        let mut min_agents = HashMap::new();
        min_agents.insert(CustomerProfile::FinTech, 10);
        min_agents.insert(CustomerProfile::Biotech, 20);
        min_agents.insert(CustomerProfile::Manufacturing, 15);

        let mut min_test_data = HashMap::new();
        min_test_data.insert(CustomerProfile::FinTech, 1000);
        min_test_data.insert(CustomerProfile::Biotech, 500);
        min_test_data.insert(CustomerProfile::Manufacturing, 1000);

        Self {
            min_agents,
            min_test_data,
        }
    }

    /// Validate environment configuration
    pub fn validate(&self, env: &PilotEnvironment) -> Result<ValidationReport, DeploymentError> {
        let mut errors = Vec::new();
        let mut warnings = Vec::new();

        // Check minimum agents
        if let Some(&min_agents) = self.min_agents.get(&env.customer) {
            if env.num_agents < min_agents {
                errors.push(format!(
                    "Insufficient agents: {} < {} required for {:?}",
                    env.num_agents, min_agents, env.customer
                ));
            }
        }

        // Check minimum test data
        if let Some(&min_data) = self.min_test_data.get(&env.customer) {
            if env.test_data_count < min_data {
                errors.push(format!(
                    "Insufficient test data: {} < {} required for {:?}",
                    env.test_data_count, min_data, env.customer
                ));
            }
        }

        // Check minimum nodes
        if env.num_nodes < 2 {
            warnings.push("Deployment with < 2 nodes is not recommended for HA".to_string());
        }

        let all_checks_passed = errors.is_empty();

        let report = ValidationReport {
            environment_id: env.id.clone(),
            all_checks_passed,
            errors: errors.clone(),
            warnings,
            validated_at: Utc::now(),
        };

        if all_checks_passed {
            Ok(report)
        } else {
            Err(DeploymentError::ValidationFailed(errors.join("; ")))
        }
    }

    /// Check if environment is ready for deployment
    pub fn is_environment_ready(&self, env: &PilotEnvironment) -> bool {
        self.validate(env).is_ok()
    }
}

impl Default for EnvironmentValidator {
    fn default() -> Self {
        Self::new()
    }
}

/// Generate Terraform configuration for customer environment
pub fn generate_terraform_config(env: &PilotEnvironment, _config: &DeploymentConfig) -> String {
    let base_subnet = match env.customer {
        CustomerProfile::FinTech => "10.0.1.0/24",
        CustomerProfile::Biotech => "10.0.2.0/24",
        CustomerProfile::Manufacturing => "10.0.3.0/24",
    };

    let tf = format!(
        r#"# Terraform configuration for {} pilot deployment (ID: {})
# Generated at: {}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{}"
}}

# VPC and networking
resource "aws_vpc" "pilot_vpc" {{
  cidr_block           = "{}"
  enable_dns_hostnames = true
  tags = {{
    Name     = "pilot-vpc-{}"
    Customer = "{:?}"
  }}
}}

resource "aws_subnet" "pilot_subnet" {{
  vpc_id                  = aws_vpc.pilot_vpc.id
  cidr_block              = "{}"
  availability_zone       = "{}"
  map_public_ip_on_launch = true

  tags = {{
    Name = "pilot-subnet-{}"
  }}
}}

# Security group
resource "aws_security_group" "pilot_sg" {{
  name        = "pilot-sg-{}"
  description = "Security group for pilot deployment"
  vpc_id      = aws_vpc.pilot_vpc.id

  ingress {{
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["{}"]
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}

  tags = {{
    Name = "pilot-sg-{}"
  }}
}}

# Compute instances
resource "aws_instance" "pilot_nodes" {{
  count           = {}
  ami             = "ami-0c55b159cbfafe1f0"  # Ubuntu 22.04 LTS
  instance_type   = "c6i.4xlarge"
  subnet_id       = aws_subnet.pilot_subnet.id
  security_groups = [aws_security_group.pilot_sg.id]

  tags = {{
    Name = "pilot-node-{}-${{count.index + 1}}"
  }}

  depends_on = [aws_subnet.pilot_subnet]
}}

# Outputs
output "instance_ids" {{
  value = aws_instance.pilot_nodes[*].id
}}

output "instance_ips" {{
  value = aws_instance.pilot_nodes[*].private_ip
}}

output "vpc_id" {{
  value = aws_vpc.pilot_vpc.id
}}
"#,
        format!("{:?}", env.customer).to_lowercase(),
        env.id,
        Utc::now().to_rfc3339(),
        env.deployment_region,
        env.network_config.vpc_cidr,
        env.id,
        format!("{:?}", env.customer),
        base_subnet,
        format!("{}a", env.deployment_region),
        env.id,
        env.id,
        base_subnet,
        env.id,
        env.num_nodes,
        env.id,
    );

    tf
}

/// Manifest for deployed pilot environment
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentManifest {
    pub environment_id: String,
    pub customer: CustomerProfile,
    pub deployment_timestamp: DateTime<Utc>,
    pub instance_ids: Vec<String>,
    pub instance_ips: Vec<String>,
    pub num_agents_deployed: usize,
    pub test_data_loaded: bool,
    pub validation_status: String,
}

impl DeploymentManifest {
    pub fn new(env: &PilotEnvironment) -> Self {
        Self {
            environment_id: env.id.clone(),
            customer: env.customer,
            deployment_timestamp: Utc::now(),
            instance_ids: Vec::new(),
            instance_ips: Vec::new(),
            num_agents_deployed: env.num_agents,
            test_data_loaded: false,
            validation_status: "pending".to_string(),
        }
    }
}

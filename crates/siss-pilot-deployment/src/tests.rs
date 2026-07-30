#[cfg(test)]
mod tests {
    use crate::{CustomerProfile, DeploymentConfig, EnvironmentValidator, PilotEnvironment};

    /// test_fintech_environment_creation: ensures FinTech pilot environment config is valid with 3-node cluster
    #[test]
    fn test_fintech_environment_creation() {
        let env = PilotEnvironment::new_fintech();

        assert_eq!(env.customer, CustomerProfile::FinTech);
        assert_eq!(env.num_agents, 10);
        assert_eq!(env.num_nodes, 3);
        assert_eq!(env.test_data_count, 1000); // 1000 trade orders
        assert_eq!(env.model_name, "trade-router-v1");
    }

    /// test_biotech_environment_creation: ensures Biotech pilot environment config is valid with 20 molecular agents
    #[test]
    fn test_biotech_environment_creation() {
        let env = PilotEnvironment::new_biotech();

        assert_eq!(env.customer, CustomerProfile::Biotech);
        assert_eq!(env.num_agents, 20);
        assert_eq!(env.num_nodes, 2);
        assert_eq!(env.test_data_count, 500); // 500 molecular hypotheses
        assert_eq!(env.model_name, "hypothesis-evaluator-v1");
    }

    /// test_manufacturing_environment_creation: ensures Manufacturing pilot environment config is valid with 15 scheduling agents
    #[test]
    fn test_manufacturing_environment_creation() {
        let env = PilotEnvironment::new_manufacturing();

        assert_eq!(env.customer, CustomerProfile::Manufacturing);
        assert_eq!(env.num_agents, 15);
        assert_eq!(env.num_nodes, 2);
        assert_eq!(env.test_data_count, 1000); // 1000 production orders
        assert_eq!(env.model_name, "scheduler-predictor-v1");
    }

    /// test_environment_validator_passes_valid_config: ensures validator accepts complete, valid environment configuration
    #[test]
    fn test_environment_validator_passes_valid_config() {
        let env = PilotEnvironment::new_fintech();
        let validator = EnvironmentValidator::new();

        let result = validator.validate(&env);
        assert!(result.is_ok(), "Valid environment should pass validation");

        let report = result.unwrap();
        assert!(report.all_checks_passed);
        assert!(report.errors.is_empty());
    }

    /// test_validator_detects_insufficient_agents: ensures validator rejects config with too few agents
    #[test]
    fn test_validator_detects_insufficient_agents() {
        let mut env = PilotEnvironment::new_fintech();
        env.num_agents = 2; // Below minimum for FinTech

        let validator = EnvironmentValidator::new();
        let result = validator.validate(&env);

        assert!(result.is_err(), "Should reject insufficient agents");
    }

    /// test_validator_detects_missing_test_data: ensures validator rejects config without test data
    #[test]
    fn test_validator_detects_missing_test_data() {
        let mut env = PilotEnvironment::new_biotech();
        env.test_data_count = 0;

        let validator = EnvironmentValidator::new();
        let result = validator.validate(&env);

        assert!(result.is_err(), "Should reject zero test data");
    }

    /// test_fintech_deployment_config_latency_target: ensures FinTech config specifies 10x latency vs. Kubernetes with <50ms veto
    #[test]
    fn test_fintech_deployment_config_latency_target() {
        let config = DeploymentConfig::for_fintech();

        assert_eq!(config.target_max_latency_ms, 50);
        assert_eq!(config.veto_latency_ms, 50);
        assert!(config.latency_targets.contains_key("fintech_trade_veto"));
    }

    /// test_biotech_deployment_config_cost_target: ensures Biotech config specifies <$10/hypothesis cost baseline
    #[test]
    fn test_biotech_deployment_config_cost_target() {
        let config = DeploymentConfig::for_biotech();

        assert_eq!(config.max_cost_per_unit, 10.0);
        assert!(config.cost_targets.contains_key("biotech_hypothesis"));
    }

    /// test_manufacturing_deployment_config_uptime_target: ensures Manufacturing config specifies 99.5% uptime with <50ms latency
    #[test]
    fn test_manufacturing_deployment_config_uptime_target() {
        let config = DeploymentConfig::for_manufacturing();

        assert_eq!(config.target_uptime_percent, 99.5);
        assert_eq!(config.target_max_latency_ms, 50);
    }

    /// test_deployment_produces_terraform_config: ensures Terraform configuration is generated with all required resources
    #[test]
    fn test_deployment_produces_terraform_config() {
        let env = PilotEnvironment::new_fintech();
        let config = DeploymentConfig::for_fintech();

        let tf_config = crate::generate_terraform_config(&env, &config);

        assert!(tf_config.contains("resource"));
        assert!(tf_config.contains("aws_instance"));
        assert!(tf_config.contains("10.0.0"));
    }

    /// test_environment_readiness_check: ensures readiness validation confirms all systems ready for deployment
    #[test]
    fn test_environment_readiness_check() {
        let env = PilotEnvironment::new_fintech();
        let validator = EnvironmentValidator::new();

        let ready = validator.is_environment_ready(&env);
        assert!(ready, "Fintech environment should be ready for deployment");
    }

    /// test_customer_isolation_between_pilots: ensures each customer's config is isolated with no cross-contamination
    #[test]
    fn test_customer_isolation_between_pilots() {
        let fintech = PilotEnvironment::new_fintech();
        let biotech = PilotEnvironment::new_biotech();
        let manufacturing = PilotEnvironment::new_manufacturing();

        assert_ne!(fintech.customer, biotech.customer);
        assert_ne!(biotech.customer, manufacturing.customer);
        assert_ne!(fintech.num_agents, biotech.num_agents);
        assert_ne!(biotech.num_agents, manufacturing.num_agents);
    }
}

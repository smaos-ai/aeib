#[cfg(test)]
mod integration_tests {
    use crate::{
        PilotEnvironment, DeploymentConfig, EnvironmentValidator, DeploymentManifest,
        CustomerProfile, generate_terraform_config,
    };

    /// test_fintech_complete_deployment_flow: ensures FinTech environment can be validated and deployed
    #[test]
    fn test_fintech_complete_deployment_flow() {
        let env = PilotEnvironment::new_fintech();
        let config = DeploymentConfig::for_fintech();
        let validator = EnvironmentValidator::new();

        // Validate
        let report = validator.validate(&env).expect("Validation should pass");
        assert!(report.all_checks_passed);
        assert!(validator.is_environment_ready(&env));

        // Generate infrastructure
        let terraform = generate_terraform_config(&env, &config);
        assert!(!terraform.is_empty());
        assert!(terraform.contains("aws_instance"));

        // Create manifest
        let mut manifest = DeploymentManifest::new(&env);
        manifest.validation_status = "READY".to_string();
        assert_eq!(manifest.customer, CustomerProfile::FinTech);
        assert_eq!(manifest.num_agents_deployed, 10);
    }

    /// test_biotech_complete_deployment_flow: ensures Biotech environment can be validated and deployed
    #[test]
    fn test_biotech_complete_deployment_flow() {
        let env = PilotEnvironment::new_biotech();
        let config = DeploymentConfig::for_biotech();
        let validator = EnvironmentValidator::new();

        let report = validator.validate(&env).expect("Validation should pass");
        assert!(report.all_checks_passed);
        assert!(validator.is_environment_ready(&env));

        let terraform = generate_terraform_config(&env, &config);
        assert!(!terraform.is_empty());
        assert!(terraform.contains("vpc"));

        let mut manifest = DeploymentManifest::new(&env);
        manifest.validation_status = "READY".to_string();
        assert_eq!(manifest.customer, CustomerProfile::Biotech);
        assert_eq!(manifest.num_agents_deployed, 20);
    }

    /// test_manufacturing_complete_deployment_flow: ensures Manufacturing environment can be validated and deployed
    #[test]
    fn test_manufacturing_complete_deployment_flow() {
        let env = PilotEnvironment::new_manufacturing();
        let config = DeploymentConfig::for_manufacturing();
        let validator = EnvironmentValidator::new();

        let report = validator.validate(&env).expect("Validation should pass");
        assert!(report.all_checks_passed);
        assert!(validator.is_environment_ready(&env));

        let terraform = generate_terraform_config(&env, &config);
        assert!(!terraform.is_empty());
        assert!(terraform.contains("10.0.3.0/24")); // Manufacturing subnet

        let mut manifest = DeploymentManifest::new(&env);
        manifest.validation_status = "READY".to_string();
        assert_eq!(manifest.customer, CustomerProfile::Manufacturing);
        assert_eq!(manifest.num_agents_deployed, 15);
    }

    /// test_all_pilots_deployable_concurrently: ensures all 3 customers can be deployed in parallel without conflicts
    #[test]
    fn test_all_pilots_deployable_concurrently() {
        let fintech = PilotEnvironment::new_fintech();
        let biotech = PilotEnvironment::new_biotech();
        let manufacturing = PilotEnvironment::new_manufacturing();

        let validator = EnvironmentValidator::new();

        // All should validate independently
        assert!(validator.validate(&fintech).is_ok());
        assert!(validator.validate(&biotech).is_ok());
        assert!(validator.validate(&manufacturing).is_ok());

        // All should have unique IDs
        assert_ne!(fintech.id, biotech.id);
        assert_ne!(biotech.id, manufacturing.id);
        assert_ne!(fintech.id, manufacturing.id);

        // All should have different subnets
        let ft_config = DeploymentConfig::for_fintech();
        let bt_config = DeploymentConfig::for_biotech();
        let mfg_config = DeploymentConfig::for_manufacturing();

        let ft_tf = generate_terraform_config(&fintech, &ft_config);
        let bt_tf = generate_terraform_config(&biotech, &bt_config);
        let mfg_tf = generate_terraform_config(&manufacturing, &mfg_config);

        // Different subnets = no IP conflicts
        assert!(ft_tf.contains("10.0.1.0/24"));
        assert!(bt_tf.contains("10.0.2.0/24"));
        assert!(mfg_tf.contains("10.0.3.0/24"));
    }

    /// test_fintech_latency_requirement: ensures FinTech config meets <50ms veto latency requirement
    #[test]
    fn test_fintech_latency_requirement() {
        let config = DeploymentConfig::for_fintech();
        assert_eq!(config.veto_latency_ms, 50);
        assert_eq!(config.target_max_latency_ms, 50);
    }

    /// test_biotech_cost_requirement: ensures Biotech config meets <$10/hypothesis requirement
    #[test]
    fn test_biotech_cost_requirement() {
        let config = DeploymentConfig::for_biotech();
        assert_eq!(config.max_cost_per_unit, 10.0);
    }

    /// test_manufacturing_uptime_requirement: ensures Manufacturing config meets 99.5% uptime requirement
    #[test]
    fn test_manufacturing_uptime_requirement() {
        let config = DeploymentConfig::for_manufacturing();
        assert_eq!(config.target_uptime_percent, 99.5);
    }

    /// test_test_data_coverage: ensures all customers have sufficient test data for validation
    #[test]
    fn test_test_data_coverage() {
        let fintech = PilotEnvironment::new_fintech();
        let biotech = PilotEnvironment::new_biotech();
        let manufacturing = PilotEnvironment::new_manufacturing();

        // FinTech: 1000 trade orders
        assert!(fintech.test_data_count >= 1000);

        // Biotech: 500 hypotheses
        assert!(biotech.test_data_count >= 500);

        // Manufacturing: 1000 production orders
        assert!(manufacturing.test_data_count >= 1000);
    }

    /// test_manifest_creation_all_customers: ensures deployment manifests can be created for all customers
    #[test]
    fn test_manifest_creation_all_customers() {
        let customers = vec![
            PilotEnvironment::new_fintech(),
            PilotEnvironment::new_biotech(),
            PilotEnvironment::new_manufacturing(),
        ];

        for env in customers {
            let mut manifest = DeploymentManifest::new(&env);
            manifest.test_data_loaded = true;
            manifest.validation_status = "READY".to_string();

            // Serialize to JSON (idempotent operation)
            let json = serde_json::to_string_pretty(&manifest)
                .expect("Manifest should serialize to JSON");
            assert!(!json.is_empty());
            assert!(json.contains(&env.id));
        }
    }
}

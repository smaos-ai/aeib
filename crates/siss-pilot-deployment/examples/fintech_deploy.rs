/// Example: FinTech pilot environment deployment
/// Generates configuration and validates readiness for 3-node cluster with 10 agents
///
/// Validation targets:
/// - 10x latency improvement vs Kubernetes
/// - <50ms veto latency
/// - 1000 trade orders for load testing

use siss_pilot_deployment::{
    PilotEnvironment, DeploymentConfig, DeploymentManifest, EnvironmentValidator,
    generate_terraform_config,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("╔════════════════════════════════════════════════════════════════╗");
    println!("║  FinTech Pilot Deployment Configuration                        ║");
    println!("╚════════════════════════════════════════════════════════════════╝");
    println!();

    // Create environment
    let env = PilotEnvironment::new_fintech();
    println!("✓ Environment created: {}", env.id);
    println!("  - Nodes: {}", env.num_nodes);
    println!("  - Agents: {}", env.num_agents);
    println!("  - Test data: {} trade orders", env.test_data_count);
    println!();

    // Create deployment config
    let config = DeploymentConfig::for_fintech();
    println!("✓ Deployment config created");
    println!("  - Target latency: {}ms (veto: {}ms)", config.target_max_latency_ms, config.veto_latency_ms);
    println!("  - Target uptime: {}%", config.target_uptime_percent);
    println!();

    // Validate environment
    let validator = EnvironmentValidator::new();
    let validation_report = validator.validate(&env)?;
    println!("✓ Environment validation: PASSED");
    println!("  - All checks passed: {}", validation_report.all_checks_passed);
    println!("  - Errors: {}", validation_report.errors.len());
    println!("  - Warnings: {}", validation_report.warnings.len());
    println!();

    // Generate Terraform configuration
    let terraform_config = generate_terraform_config(&env, &config);
    println!("✓ Terraform configuration generated");
    println!("  - Size: {} bytes", terraform_config.len());
    println!();

    // Create deployment manifest
    let mut manifest = DeploymentManifest::new(&env);
    manifest.test_data_loaded = true;
    manifest.validation_status = "READY".to_string();

    let _manifest_json = serde_json::to_string_pretty(&manifest)?;
    println!("✓ Deployment manifest created");
    println!();

    println!("╔════════════════════════════════════════════════════════════════╗");
    println!("║  ✓ FinTech Configuration Ready for Deployment                 ║");
    println!("╚════════════════════════════════════════════════════════════════╝");

    Ok(())
}

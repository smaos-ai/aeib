/// Demo integration for live ArgoCD deployment showcase
use crate::{ApplicationSetTemplate, ArgocdController, ClusterConfig, DoraMetrics, SyncEvent};
use chrono::Utc;

/// Demo scenario: Deploy SovereignNexus across 3 cloud providers
pub struct DemoScenario {
    pub title: String,
    pub controllers: Vec<ArgocdController>,
    pub deployment_events: Vec<SyncEvent>,
}

impl Default for DemoScenario {
    fn default() -> Self {
        Self {
            title: "SovereignNexus Multi-Cloud GitOps Deployment".to_string(),
            controllers: vec![],
            deployment_events: vec![],
        }
    }
}

impl DemoScenario {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn setup_multi_cloud() -> Self {
        let mut scenario = Self::new();

        // AWS controller
        let aws_controller = ArgocdController::new(
            ApplicationSetTemplate {
                name: "sovereign-nexus-aws".to_string(),
                namespace: "argocd".to_string(),
                source_repo: "https://github.com/SovereignNexus/deploy".to_string(),
                target_revision: "main".to_string(),
            },
            "https://github.com/SovereignNexus/deploy".to_string(),
            vec![
                ClusterConfig {
                    name: "aws-us-east-1".to_string(),
                    api_url: "https://eks-us-east-1.amazonaws.com".to_string(),
                    enabled: true,
                },
                ClusterConfig {
                    name: "aws-eu-west-1".to_string(),
                    api_url: "https://eks-eu-west-1.amazonaws.com".to_string(),
                    enabled: true,
                },
            ],
        );

        // GCP controller
        let gcp_controller = ArgocdController::new(
            ApplicationSetTemplate {
                name: "sovereign-nexus-gcp".to_string(),
                namespace: "argocd".to_string(),
                source_repo: "https://github.com/SovereignNexus/deploy".to_string(),
                target_revision: "main".to_string(),
            },
            "https://github.com/SovereignNexus/deploy".to_string(),
            vec![ClusterConfig {
                name: "gcp-europe-west1".to_string(),
                api_url: "https://gke-europe-west1.gcloud.com".to_string(),
                enabled: true,
            }],
        );

        // Azure controller
        let azure_controller = ArgocdController::new(
            ApplicationSetTemplate {
                name: "sovereign-nexus-azure".to_string(),
                namespace: "argocd".to_string(),
                source_repo: "https://github.com/SovereignNexus/deploy".to_string(),
                target_revision: "main".to_string(),
            },
            "https://github.com/SovereignNexus/deploy".to_string(),
            vec![ClusterConfig {
                name: "azure-eastus".to_string(),
                api_url: "https://aks-eastus.azure.com".to_string(),
                enabled: true,
            }],
        );

        scenario.controllers = vec![aws_controller, gcp_controller, azure_controller];
        scenario
    }

    pub fn generate_sync_events(&mut self) -> Vec<SyncEvent> {
        let commit_hash = "7f3a2c8e9b1d4f6a".to_string();
        let now = Utc::now();

        let events = vec![
            SyncEvent {
                cluster: "aws-us-east-1".to_string(),
                app_name: "sovereign-nexus".to_string(),
                commit_hash: commit_hash.clone(),
                sync_timestamp: now,
                duration_ms: 450,
                success: true,
            },
            SyncEvent {
                cluster: "aws-eu-west-1".to_string(),
                app_name: "sovereign-nexus".to_string(),
                commit_hash: commit_hash.clone(),
                sync_timestamp: now,
                duration_ms: 520,
                success: true,
            },
            SyncEvent {
                cluster: "gcp-europe-west1".to_string(),
                app_name: "sovereign-nexus".to_string(),
                commit_hash: commit_hash.clone(),
                sync_timestamp: now,
                duration_ms: 480,
                success: true,
            },
            SyncEvent {
                cluster: "azure-eastus".to_string(),
                app_name: "sovereign-nexus".to_string(),
                commit_hash: commit_hash.clone(),
                sync_timestamp: now,
                duration_ms: 510,
                success: true,
            },
        ];

        self.deployment_events = events.clone();
        events
    }

    pub fn calculate_metrics(&self) -> DoraMetrics {
        DoraMetrics::calculate_from_events(&self.deployment_events)
    }

    pub fn print_demo_report(&self) {
        println!("\n=== {} ===\n", self.title);
        println!("Controllers: {}", self.controllers.len());
        for controller in &self.controllers {
            println!(
                "  - {} ({} clusters)",
                controller.app_set_template.name,
                controller.clusters.len()
            );
        }

        println!("\nDeployment Events: {}", self.deployment_events.len());
        for event in &self.deployment_events {
            let status = if event.success {
                "✓ OK"
            } else {
                "✗ FAILED"
            };
            println!(
                "  - {} on {}: {}ms {}",
                event.app_name, event.cluster, event.duration_ms, status
            );
        }

        let metrics = self.calculate_metrics();
        println!("\nDORA Metrics:");
        println!(
            "  - Deployment Frequency: {:.2} per month",
            metrics.deployment_frequency
        );
        println!(
            "  - Lead Time for Changes: {:.0} ms",
            metrics.lead_time_for_changes
        );
        println!(
            "  - Change Failure Rate: {:.2}%",
            metrics.change_failure_rate
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_demo_scenario_setup() {
        let scenario = DemoScenario::setup_multi_cloud();
        assert_eq!(scenario.controllers.len(), 3);
        assert_eq!(
            scenario.controllers[0].clusters.len()
                + scenario.controllers[1].clusters.len()
                + scenario.controllers[2].clusters.len(),
            4
        );
    }

    #[test]
    fn test_sync_events_generation() {
        let mut scenario = DemoScenario::setup_multi_cloud();
        let events = scenario.generate_sync_events();
        assert_eq!(events.len(), 4);
        assert!(events.iter().all(|e| e.success));
    }

    #[test]
    fn test_dora_metrics_from_demo() {
        let mut scenario = DemoScenario::setup_multi_cloud();
        scenario.generate_sync_events();
        let metrics = scenario.calculate_metrics();
        assert!(metrics.deployment_frequency > 0.0);
        assert_eq!(metrics.change_failure_rate, 0.0);
    }
}

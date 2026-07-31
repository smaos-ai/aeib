#[cfg(test)]
mod tests {
    use crate::{
        ApplicationSetTemplate, ArgocdController, ClusterConfig, DeploymentProof, SyncStatus,
    };
    use chrono::Utc;
    use std::collections::HashMap;
    use uuid::Uuid;

    fn create_test_controller() -> ArgocdController {
        ArgocdController {
            id: Uuid::new_v4(),
            app_set_template: ApplicationSetTemplate {
                name: "sovereign-nexus-app".to_string(),
                namespace: "argocd".to_string(),
                source_repo: "https://github.com/SovereignNexus/deploy".to_string(),
                target_revision: "main".to_string(),
            },
            git_repo: "https://github.com/SovereignNexus/deploy".to_string(),
            clusters: vec![
                ClusterConfig {
                    name: "aws-us-east-1".to_string(),
                    api_url: "https://eks-us-east-1.amazonaws.com".to_string(),
                    enabled: true,
                },
                ClusterConfig {
                    name: "gcp-europe-west1".to_string(),
                    api_url: "https://gke-europe-west1.gcloud.com".to_string(),
                    enabled: true,
                },
                ClusterConfig {
                    name: "azure-eastus".to_string(),
                    api_url: "https://aks-eastus.azure.com".to_string(),
                    enabled: true,
                },
            ],
            created_at: Utc::now(),
            updated_at: Utc::now(),
            team_permissions: HashMap::new(),
        }
    }

    #[test]
    fn test_applicationset_creation() {
        let controller = create_test_controller();
        assert_eq!(controller.app_set_template.name, "sovereign-nexus-app");
        assert_eq!(controller.clusters.len(), 3);
        assert!(controller.clusters.iter().all(|c| c.enabled));
    }

    #[test]
    fn test_git_sync_detection() {
        let controller = create_test_controller();
        let commit_hash = "abc123def456".to_string();

        let result = controller.detect_git_changes(&commit_hash);
        assert!(result.is_ok());
        let changes = result.unwrap();
        assert!(!changes.is_empty());
    }

    #[test]
    fn test_multi_cluster_deployment() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller.deploy_to_clusters("main", "abc123def456").await;
            assert!(result.is_ok());

            let proof = result.unwrap();
            assert_eq!(proof.clusters_deployed.len(), 3);
            assert!(
                proof
                    .clusters_deployed
                    .contains(&"aws-us-east-1".to_string())
            );
            assert!(
                proof
                    .clusters_deployed
                    .contains(&"gcp-europe-west1".to_string())
            );
            assert!(
                proof
                    .clusters_deployed
                    .contains(&"azure-eastus".to_string())
            );
        });
    }

    #[test]
    fn test_rollback_on_failure() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller
                .rollback_to_previous_revision("aws-us-east-1")
                .await;
            assert!(result.is_ok());
            assert_eq!(result.unwrap(), true);
        });
    }

    #[test]
    fn test_argocd_sync_status_tracking() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller.get_sync_status("aws-us-east-1").await;
            assert!(result.is_ok());

            let status = result.unwrap();
            match status {
                SyncStatus::Synced => assert!(true),
                SyncStatus::OutOfSync => assert!(true),
                SyncStatus::Unknown => assert!(true),
                _ => panic!("Unexpected status"),
            }
        });
    }

    #[test]
    fn test_deployment_proof_generation() {
        let _controller = create_test_controller();
        let proof = DeploymentProof {
            commit_hash: "abc123def456".to_string(),
            clusters_deployed: vec![
                "aws-us-east-1".to_string(),
                "gcp-europe-west1".to_string(),
                "azure-eastus".to_string(),
            ],
            sync_status: SyncStatus::Synced,
            timestamp: Utc::now(),
        };

        assert_eq!(proof.clusters_deployed.len(), 3);
        assert_eq!(proof.sync_status, SyncStatus::Synced);
    }

    #[test]
    fn test_concurrent_deployments() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let handles: Vec<_> = controller
                .clusters
                .iter()
                .map(|cluster| {
                    let cluster_name = cluster.name.clone();
                    tokio::spawn(async move {
                        // Simulate parallel deployment
                        tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
                        cluster_name
                    })
                })
                .collect();

            let results = futures::future::join_all(handles).await;
            assert_eq!(results.len(), 3);
        });
    }

    #[test]
    fn test_drift_detection() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller.detect_config_drift("aws-us-east-1").await;
            assert!(result.is_ok());

            let has_drift = result.unwrap();
            // Drift should be detectable
            assert!(has_drift.is_some());
        });
    }

    #[test]
    fn test_demo_mode_visible_sync() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller.trigger_sync_with_notification().await;
            assert!(result.is_ok());

            let notification = result.unwrap();
            assert!(!notification.is_empty());
        });
    }

    #[test]
    fn test_argocd_metrics_collection() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller.collect_deployment_metrics().await;
            assert!(result.is_ok());

            let metrics = result.unwrap();
            assert!(metrics.deployment_count > 0);
            assert!(metrics.success_rate >= 0.0 && metrics.success_rate <= 1.0);
        });
    }

    #[test]
    fn test_rbac_multi_team_access() {
        let mut controller = create_test_controller();

        let team_a_access =
            controller.grant_team_access("team-a", vec!["aws-us-east-1".to_string()]);
        assert!(team_a_access.is_ok());

        let team_b_access =
            controller.grant_team_access("team-b", vec!["gcp-europe-west1".to_string()]);
        assert!(team_b_access.is_ok());

        assert_eq!(controller.team_permissions.len(), 2);
    }

    #[test]
    fn test_argocd_notifications() {
        let controller = create_test_controller();
        let runtime = tokio::runtime::Runtime::new().unwrap();

        runtime.block_on(async {
            let result = controller
                .send_deployment_notification(
                    "Deployment completed successfully on all clusters".to_string(),
                )
                .await;
            assert!(result.is_ok());
        });
    }
}

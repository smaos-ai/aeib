use serde::{Deserialize, Serialize};

/// ArgoCD ApplicationSet configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSet {
    pub api_version: String,
    pub kind: String,
    pub metadata: ApplicationSetMetadata,
    pub spec: ApplicationSetSpec,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSetMetadata {
    pub name: String,
    pub namespace: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSetSpec {
    pub generators: Vec<Generator>,
    pub template: ApplicationTemplate,
    pub sync_policy: Option<SyncPolicy>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum Generator {
    #[serde(rename = "git")]
    Git(GitGenerator),
    #[serde(rename = "list")]
    List(ListGenerator),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitGenerator {
    pub repo_url: String,
    pub revision: String,
    pub directories: Vec<DirectoryPattern>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListGenerator {
    pub elements: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DirectoryPattern {
    pub path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationTemplate {
    pub metadata: TemplateMetadata,
    pub spec: ApplicationSpec,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateMetadata {
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSpec {
    pub project: String,
    pub source: Source,
    pub destination: Destination,
    pub sync_policy: Option<SyncPolicy>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Source {
    pub repo_url: String,
    pub target_revision: String,
    pub path: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Destination {
    pub server: String,
    pub namespace: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncPolicy {
    pub automated: Option<AutomatedSyncPolicy>,
    pub sync_options: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutomatedSyncPolicy {
    pub prune: bool,
    pub self_heal: bool,
}

impl ApplicationSet {
    pub fn new(name: String, namespace: String) -> Self {
        Self {
            api_version: "argoproj.io/v1alpha1".to_string(),
            kind: "ApplicationSet".to_string(),
            metadata: ApplicationSetMetadata { name, namespace },
            spec: ApplicationSetSpec {
                generators: vec![],
                template: ApplicationTemplate {
                    metadata: TemplateMetadata {
                        name: "default".to_string(),
                    },
                    spec: ApplicationSpec {
                        project: "default".to_string(),
                        source: Source {
                            repo_url: "".to_string(),
                            target_revision: "main".to_string(),
                            path: ".".to_string(),
                        },
                        destination: Destination {
                            server: "https://kubernetes.default.svc".to_string(),
                            namespace: "default".to_string(),
                        },
                        sync_policy: None,
                    },
                },
                sync_policy: None,
            },
        }
    }

    pub fn to_yaml(&self) -> Result<String, serde_yaml::Error> {
        serde_yaml::to_string(self)
    }
}

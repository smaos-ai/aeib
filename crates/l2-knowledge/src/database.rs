use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyDocument {
    pub article_id: String,
    pub article_text: String,
    pub interpretation: String,
    pub keywords: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceDeadline {
    pub deadline: String,
    pub regulation: String,
    pub article_number: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceRisk {
    pub risk_name: String,
    pub severity: String,
    pub mitigation_strategy: String,
}

pub struct KnowledgeDb {
    policies: Vec<PolicyDocument>,
    deadlines: Vec<ComplianceDeadline>,
    risks: Vec<GovernanceRisk>,
}

impl KnowledgeDb {
    pub fn new() -> Self {
        Self {
            policies: Vec::new(),
            deadlines: Vec::new(),
            risks: Vec::new(),
        }
    }

    pub fn add_policy(&mut self, policy: PolicyDocument) {
        self.policies.push(policy);
    }

    pub fn get_policies(&self) -> &[PolicyDocument] {
        &self.policies
    }

    pub fn query_policies(&self, query: &str) -> Vec<&PolicyDocument> {
        self.policies
            .iter()
            .filter(|p| {
                p.article_text.to_lowercase().contains(&query.to_lowercase())
                    || p.keywords.iter().any(|k| k.to_lowercase().contains(&query.to_lowercase()))
            })
            .collect()
    }

    pub fn add_deadline(&mut self, deadline: ComplianceDeadline) {
        self.deadlines.push(deadline);
    }

    pub fn get_upcoming_deadlines(&self) -> Vec<&ComplianceDeadline> {
        self.deadlines.iter().collect()
    }

    pub fn add_risk(&mut self, risk: GovernanceRisk) {
        self.risks.push(risk);
    }

    pub fn get_critical_risks(&self) -> Vec<&GovernanceRisk> {
        self.risks
            .iter()
            .filter(|r| r.severity == "CRITICAL" || r.severity == "HIGH")
            .collect()
    }
}

impl Default for KnowledgeDb {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_policy() {
        let mut db = KnowledgeDb::new();
        let policy = PolicyDocument {
            article_id: "Article50".to_string(),
            article_text: "Transparency in AI systems".to_string(),
            interpretation: "Must document all decisions".to_string(),
            keywords: vec!["transparency".to_string(), "documentation".to_string()],
        };
        db.add_policy(policy);
        assert_eq!(db.get_policies().len(), 1);
    }

    #[test]
    fn test_query_policies() {
        let mut db = KnowledgeDb::new();
        db.add_policy(PolicyDocument {
            article_id: "Article50".to_string(),
            article_text: "Transparency in AI systems".to_string(),
            interpretation: "Must document".to_string(),
            keywords: vec!["transparency".to_string()],
        });

        let results = db.query_policies("transparency");
        assert_eq!(results.len(), 1);
    }

    #[test]
    fn test_add_deadline() {
        let mut db = KnowledgeDb::new();
        db.add_deadline(ComplianceDeadline {
            deadline: "2027-12-02".to_string(),
            regulation: "EU AI Act".to_string(),
            article_number: "Annex III".to_string(),
            description: "Compliance deadline for hotels/spas".to_string(),
        });
        assert_eq!(db.get_upcoming_deadlines().len(), 1);
    }

    #[test]
    fn test_add_risk() {
        let mut db = KnowledgeDb::new();
        db.add_risk(GovernanceRisk {
            risk_name: "Visibility Gap".to_string(),
            severity: "CRITICAL".to_string(),
            mitigation_strategy: "Implement logging at all decision points".to_string(),
        });
        let critical = db.get_critical_risks();
        assert_eq!(critical.len(), 1);
    }
}

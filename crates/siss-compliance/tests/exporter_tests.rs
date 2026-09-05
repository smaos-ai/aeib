//! Task 1: L8 Dossier Exporter Tests
//! Feed 100+ decisions from AP2 ledger → extract → Annex format → KMS signature
//! 50 LOC test suite

use std::collections::HashMap;
use chrono::Utc;
use uuid::Uuid;

#[derive(Debug, Clone)]
struct MockLedgerDecision {
    decision_id: String,
    timestamp: i64,
    case_type: String,
    outcome: bool,
    score: f64,
    evidence: HashMap<String, String>,
}

impl MockLedgerDecision {
    fn new(case_type: &str, outcome: bool, score: f64) -> Self {
        Self {
            decision_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().timestamp(),
            case_type: case_type.to_string(),
            outcome,
            score,
            evidence: HashMap::new(),
        }
    }
}

// Mock L8 Dossier Exporter
struct L8DossierExporter {
    decisions: Vec<MockLedgerDecision>,
}

impl L8DossierExporter {
    fn new() -> Self {
        Self {
            decisions: Vec::new(),
        }
    }

    fn load_from_ledger(&mut self, decisions: Vec<MockLedgerDecision>) -> Result<usize, String> {
        if decisions.is_empty() {
            return Err("No decisions provided".to_string());
        }
        let count = decisions.len();
        self.decisions = decisions;
        Ok(count)
    }

    fn extract_for_annex(&self, annex_type: &str) -> Result<Vec<MockLedgerDecision>, String> {
        if self.decisions.is_empty() {
            return Err("No decisions loaded".to_string());
        }

        let filtered: Vec<_> = self.decisions
            .iter()
            .filter(|d| d.case_type == annex_type || annex_type == "all")
            .cloned()
            .collect();

        if filtered.is_empty() {
            return Err(format!("No {} decisions found", annex_type));
        }

        Ok(filtered)
    }

    fn format_for_dossier(&self) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to format".to_string());
        }

        let json = serde_json::json!({
            "decisions_count": self.decisions.len(),
            "case_types": self.decisions.iter().map(|d| d.case_type.clone()).collect::<Vec<_>>(),
            "avg_score": self.decisions.iter().map(|d| d.score).sum::<f64>() / self.decisions.len() as f64,
        });

        Ok(json.to_string())
    }

    fn add_kms_signature(&mut self, signature: String) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to sign".to_string());
        }

        let signed_dossier = serde_json::json!({
            "decisions": self.decisions.len(),
            "kms_signature": signature,
            "signed_at": Utc::now().timestamp(),
        });

        Ok(signed_dossier.to_string())
    }

    fn decision_count(&self) -> usize {
        self.decisions.len()
    }
}

// ============ TESTS ============

#[test]
fn test_exporter_creation() {
    let exporter = L8DossierExporter::new();
    assert_eq!(exporter.decision_count(), 0);
}

#[test]
fn test_load_from_ledger_empty() {
    let mut exporter = L8DossierExporter::new();
    let result = exporter.load_from_ledger(vec![]);
    assert!(result.is_err());
}

#[test]
fn test_load_from_ledger_success() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..50)
        .map(|_| MockLedgerDecision::new("hotel", true, 0.95))
        .collect();

    let result = exporter.load_from_ledger(decisions);
    assert!(result.is_ok());
    assert_eq!(result.unwrap(), 50);
    assert_eq!(exporter.decision_count(), 50);
}

#[test]
fn test_load_100_decisions() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..100)
        .map(|i| {
            let case_type = match i % 3 {
                0 => "hotel",
                1 => "glass",
                _ => "auto",
            };
            MockLedgerDecision::new(case_type, i % 2 == 0, 0.90 + (i as f64 / 1000.0))
        })
        .collect();

    let result = exporter.load_from_ledger(decisions);
    assert!(result.is_ok());
    assert_eq!(exporter.decision_count(), 100);
}

#[test]
fn test_extract_for_annex_no_decisions() {
    let exporter = L8DossierExporter::new();
    let result = exporter.extract_for_annex("hotel");
    assert!(result.is_err());
}

#[test]
fn test_extract_for_annex_hotel() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..100)
        .map(|i| {
            let case_type = match i % 3 {
                0 => "hotel",
                1 => "glass",
                _ => "auto",
            };
            MockLedgerDecision::new(case_type, true, 0.95)
        })
        .collect();

    exporter.load_from_ledger(decisions).unwrap();
    let result = exporter.extract_for_annex("hotel");
    assert!(result.is_ok());
    let extracted = result.unwrap();
    assert!(extracted.len() > 0);
    assert!(extracted.iter().all(|d| d.case_type == "hotel"));
}

#[test]
fn test_extract_for_annex_glass() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..100)
        .map(|i| {
            let case_type = match i % 3 {
                0 => "hotel",
                1 => "glass",
                _ => "auto",
            };
            MockLedgerDecision::new(case_type, true, 0.92)
        })
        .collect();

    exporter.load_from_ledger(decisions).unwrap();
    let result = exporter.extract_for_annex("glass");
    assert!(result.is_ok());
    let extracted = result.unwrap();
    assert!(extracted.iter().all(|d| d.case_type == "glass"));
}

#[test]
fn test_extract_for_annex_auto() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..100)
        .map(|i| {
            let case_type = match i % 3 {
                0 => "hotel",
                1 => "glass",
                _ => "auto",
            };
            MockLedgerDecision::new(case_type, i % 2 == 0, 0.90)
        })
        .collect();

    exporter.load_from_ledger(decisions).unwrap();
    let result = exporter.extract_for_annex("auto");
    assert!(result.is_ok());
}

#[test]
fn test_format_for_dossier_no_decisions() {
    let exporter = L8DossierExporter::new();
    let result = exporter.format_for_dossier();
    assert!(result.is_err());
}

#[test]
fn test_format_for_dossier_success() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..50)
        .map(|_| MockLedgerDecision::new("hotel", true, 0.95))
        .collect();

    exporter.load_from_ledger(decisions).unwrap();
    let result = exporter.format_for_dossier();
    assert!(result.is_ok());
    let json_str = result.unwrap();
    assert!(json_str.contains("decisions_count"));
    assert!(json_str.contains("50"));
}

#[test]
fn test_add_kms_signature() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..50)
        .map(|_| MockLedgerDecision::new("hotel", true, 0.95))
        .collect();

    exporter.load_from_ledger(decisions).unwrap();
    let sig = "mock_ed25519_signature_abc123".to_string();
    let result = exporter.add_kms_signature(sig);

    assert!(result.is_ok());
    let signed = result.unwrap();
    assert!(signed.contains("kms_signature"));
    assert!(signed.contains("mock_ed25519"));
}

#[test]
fn test_kms_signature_no_decisions() {
    let mut exporter = L8DossierExporter::new();
    let result = exporter.add_kms_signature("signature".to_string());
    assert!(result.is_err());
}

#[test]
fn test_end_to_end_100_decisions() {
    let mut exporter = L8DossierExporter::new();
    let decisions: Vec<_> = (0..100)
        .map(|i| {
            let case_type = match i % 3 {
                0 => "hotel",
                1 => "glass",
                _ => "auto",
            };
            MockLedgerDecision::new(case_type, i % 2 == 0, 0.90 + (i as f64 / 500.0))
        })
        .collect();

    // Load from ledger
    let loaded = exporter.load_from_ledger(decisions).unwrap();
    assert_eq!(loaded, 100);

    // Extract for each annex
    let hotel_decisions = exporter.extract_for_annex("hotel").unwrap();
    assert!(hotel_decisions.len() > 0);

    let glass_decisions = exporter.extract_for_annex("glass").unwrap();
    assert!(glass_decisions.len() > 0);

    let auto_decisions = exporter.extract_for_annex("auto").unwrap();
    assert!(auto_decisions.len() > 0);

    // Format for dossier
    let formatted = exporter.format_for_dossier().unwrap();
    assert!(formatted.contains("decisions_count"));

    // Add signature
    let signed = exporter.add_kms_signature("test_sig".to_string()).unwrap();
    assert!(signed.contains("kms_signature"));
}

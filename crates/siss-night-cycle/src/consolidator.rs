use crate::failure_analyzer::FailureAnalyzer;
use crate::offline_verifier::OfflineVerifier;
use crate::config_evolution::ConfigEvolution;
use crate::metrics::MetricsDb;
use std::path::PathBuf;

pub struct NightCycleConsolidator {
    exec_log_path: PathBuf,
    metrics_db_path: PathBuf,
    config_log_path: PathBuf,
    verification_report_path: PathBuf,
}

impl NightCycleConsolidator {
    pub fn new(
        exec_log_path: PathBuf,
        metrics_db_path: PathBuf,
        config_log_path: PathBuf,
        verification_report_path: PathBuf,
    ) -> Self {
        Self {
            exec_log_path,
            metrics_db_path,
            config_log_path,
            verification_report_path,
        }
    }

    pub fn run_consolidation(&self) -> std::io::Result<()> {
        let mut analyzer = FailureAnalyzer::from_log_file(&self.exec_log_path)?;
        analyzer.analyze();

        let db = MetricsDb::new(Some(self.metrics_db_path.clone()))
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;

        let verifier = OfflineVerifier::new(analyzer, db);
        let report = verifier.verify()?;

        verifier.write_report(&report, &self.verification_report_path)?;

        self.apply_safe_mutations(&report)?;

        Ok(())
    }

    fn apply_safe_mutations(
        &self,
        report: &crate::offline_verifier::VerificationReport,
    ) -> std::io::Result<()> {
        let mut evolution = ConfigEvolution::new(self.config_log_path.clone())?;

        for suggestion in &report.suggestions {
            if suggestion.confidence >= 0.80 {
                evolution.record_mutation(
                    &suggestion.category,
                    &suggestion.current_value,
                    &suggestion.recommended_value,
                    &suggestion.rationale,
                )?;

                evolution.apply_mutation(evolution.get_mutations().len() - 1)?;

                crate::ledger::append_audit(
                    "config_mutation_applied",
                    &format!(
                        "{}: {} → {} (confidence: {:.2})",
                        suggestion.category,
                        suggestion.current_value,
                        suggestion.recommended_value,
                        suggestion.confidence
                    ),
                )?;
            } else {
                crate::ledger::append_audit(
                    "config_mutation_pending",
                    &format!(
                        "{}: {} → {} (confidence: {:.2}, below threshold)",
                        suggestion.category,
                        suggestion.current_value,
                        suggestion.recommended_value,
                        suggestion.confidence
                    ),
                )?;
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_consolidator_initialization() {
        let exec_log = NamedTempFile::new().unwrap();
        let metrics_db = NamedTempFile::new().unwrap();
        let config_log = NamedTempFile::new().unwrap();
        let verification = NamedTempFile::new().unwrap();

        let consolidator = NightCycleConsolidator::new(
            exec_log.path().to_path_buf(),
            metrics_db.path().to_path_buf(),
            config_log.path().to_path_buf(),
            verification.path().to_path_buf(),
        );

        assert_eq!(consolidator.exec_log_path, exec_log.path());
    }

    #[test]
    fn test_consolidation_run() {
        let mut exec_log = NamedTempFile::new().unwrap();
        writeln!(
            exec_log,
            r#"{{"event":"watchdog_alert","message":"Test failed (attempt 1/2)","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.666775+00:00"}}"#
        )
        .unwrap();
        writeln!(
            exec_log,
            r#"{{"event":"watchdog","message":"test passed","source":"siss-night-cycle","timestamp":"2026-05-27T10:41:05.478108+00:00"}}"#
        )
        .unwrap();
        exec_log.flush().unwrap();

        let metrics_db = NamedTempFile::new().unwrap();
        let config_log = NamedTempFile::new().unwrap();
        let verification = NamedTempFile::new().unwrap();

        let consolidator = NightCycleConsolidator::new(
            exec_log.path().to_path_buf(),
            metrics_db.path().to_path_buf(),
            config_log.path().to_path_buf(),
            verification.path().to_path_buf(),
        );

        let result = consolidator.run_consolidation();
        assert!(result.is_ok());
    }
}

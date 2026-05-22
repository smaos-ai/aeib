/// Phase 61: Coordinated Graph Rename Gate — Mandatory Dry-Run Enforcement

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RenameScope {
    SingleFile { path: String },
    ModulePath { module: String },
    FullCrate,
}

#[derive(Debug, Clone)]
pub struct RenameTarget {
    pub old_name: String,
    pub new_name: String,
    pub scope: RenameScope,
}

#[derive(Debug, Clone)]
pub struct RenamePreview {
    pub affected_files: usize,
    pub total_changes: usize,
    pub confidence: f64,
    pub is_safe: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RenameError {
    DryRunMandatory,
    LowConfidence { required: i64, actual: i64 },
    RenameBlocked { reason: String },
}

#[derive(Debug, Clone)]
pub struct CoordinatedRenameGate {
    pub confidence_threshold: f64,
    pub require_dry_run: bool,
}

impl Default for CoordinatedRenameGate {
    fn default() -> Self {
        CoordinatedRenameGate {
            confidence_threshold: 0.85,
            require_dry_run: true,
        }
    }
}

impl CoordinatedRenameGate {
    pub fn new(confidence_threshold: f64, require_dry_run: bool) -> Self {
        CoordinatedRenameGate {
            confidence_threshold,
            require_dry_run,
        }
    }

    pub fn plan_rename(
        &self,
        target: &RenameTarget,
        dry_run: bool,
    ) -> Result<RenamePreview, RenameError> {
        if self.require_dry_run && !dry_run {
            return Err(RenameError::DryRunMandatory);
        }

        if target.old_name.is_empty() || target.new_name.is_empty() {
            return Err(RenameError::RenameBlocked {
                reason: "empty_symbol_name".to_string(),
            });
        }

        const SINGLE_FILE_CAP: usize = 50;

        let (affected_files, total_changes, confidence) = match &target.scope {
            RenameScope::SingleFile { .. } => (1, 1, 0.95),
            RenameScope::ModulePath { .. } => (5, 20, 0.88),
            RenameScope::FullCrate => (25, 200, 0.70),
        };

        let scope_is_single = matches!(target.scope, RenameScope::SingleFile { .. });
        let confidence_ok = confidence >= self.confidence_threshold;
        let size_ok = total_changes < SINGLE_FILE_CAP || !scope_is_single;

        let is_safe = scope_is_single && size_ok && confidence_ok;

        Ok(RenamePreview {
            affected_files,
            total_changes,
            confidence,
            is_safe,
        })
    }

    pub fn execute_rename(&self, preview: &RenamePreview) -> Result<usize, RenameError> {
        let required = (self.confidence_threshold * 100.0) as i64;
        let actual = (preview.confidence * 100.0) as i64;

        if actual < required {
            return Err(RenameError::LowConfidence { required, actual });
        }

        if !preview.is_safe {
            return Err(RenameError::RenameBlocked {
                reason: "preview_not_safe".to_string(),
            });
        }

        Ok(preview.total_changes)
    }
}

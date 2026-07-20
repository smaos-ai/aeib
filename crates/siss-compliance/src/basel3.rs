use std::collections::HashMap;

/// Basel III Three Pillars
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum BaselPillar {
    /// Pillar 1: Minimum capital requirements
    Pillar1CapitalAdequacy,
    /// Pillar 2: Supervisory review and internal assessment
    Pillar2SupervisoryReview,
    /// Pillar 3: Market discipline through public disclosure
    Pillar3Disclosure,
}

/// Maps Basel III compliance controls to their pillar and implementation status
pub struct BaselIiiMapper {
    /// control_id → pillar tag (e.g., "P1", "P2", "P3")
    controls: HashMap<String, String>,
}

impl BaselIiiMapper {
    /// Creates an empty mapper
    pub fn new() -> Self {
        Self {
            controls: HashMap::new(),
        }
    }

    /// Inserts a control mapped to a pillar tag
    pub fn insert(&mut self, control_id: impl Into<String>, pillar_tag: impl Into<String>) {
        self.controls.insert(control_id.into(), pillar_tag.into());
    }

    /// Fraction of controls belonging to `pillar` that are present (0.0 – 1.0).
    /// With an empty mapper, returns 0.0 for any pillar.
    pub fn pillar_score(&self, pillar: BaselPillar) -> f64 {
        let tag = pillar_tag(pillar);
        let total_for_pillar = self
            .controls
            .values()
            .filter(|v| v.as_str() == tag)
            .count();
        if total_for_pillar == 0 {
            return 0.0;
        }
        total_for_pillar as f64 / total_for_pillar as f64
    }

    /// Capital Adequacy Ratio = capital / risk_weighted_assets.
    /// Basel III minimum: 0.08 (8%).
    /// Returns `Err` if assets == 0 to avoid division by zero.
    pub fn capital_adequacy_ratio(&self, assets: u64, capital: u64) -> Result<f64, &'static str> {
        if assets == 0 {
            return Err("risk-weighted assets cannot be zero");
        }
        Ok(capital as f64 / assets as f64)
    }

    /// Returns true when the CAR meets or exceeds the 8% Basel III minimum.
    pub fn meets_minimum_capital(&self, assets: u64, capital: u64) -> bool {
        self.capital_adequacy_ratio(assets, capital)
            .map(|r| r >= 0.08)
            .unwrap_or(false)
    }
}

impl Default for BaselIiiMapper {
    fn default() -> Self {
        Self::new()
    }
}

fn pillar_tag(pillar: BaselPillar) -> &'static str {
    match pillar {
        BaselPillar::Pillar1CapitalAdequacy => "P1",
        BaselPillar::Pillar2SupervisoryReview => "P2",
        BaselPillar::Pillar3Disclosure => "P3",
    }
}

use std::collections::HashMap;

use crate::model::modality::Modality;
use crate::orchestrator::evolution_gate::Verdict;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RouteTarget {
    Shadow,
    Baseline,
}

pub type RoutingDecision = HashMap<Modality, RouteTarget>;

pub struct OmniRoute;

impl OmniRoute {
    pub fn new() -> Self {
        OmniRoute
    }

    pub fn route(&self, verdict: &Verdict) -> RoutingDecision {
        [Modality::Text, Modality::Vision, Modality::Audio]
            .into_iter()
            .map(|m| {
                let target = if verdict.approved_for_modalities.contains(&m) {
                    RouteTarget::Shadow
                } else {
                    RouteTarget::Baseline
                };
                (m, target)
            })
            .collect()
    }
}

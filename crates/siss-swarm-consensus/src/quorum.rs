use crate::errors::BftConsensusError;

pub struct QuorumValidator {
    total_agents: usize,
    consensus_threshold: f64,
}

impl QuorumValidator {
    pub fn new(total_agents: usize, consensus_threshold: f64) -> Result<Self, BftConsensusError> {
        if total_agents == 0 {
            return Err(BftConsensusError::EngineStateError(
                "Total agents must be > 0".to_string(),
            ));
        }
        if !(0.0..=1.0).contains(&consensus_threshold) {
            return Err(BftConsensusError::EngineStateError(
                "Consensus threshold must be between 0.0 and 1.0".to_string(),
            ));
        }
        Ok(Self {
            total_agents,
            consensus_threshold,
        })
    }

    pub fn required_commits(&self) -> usize {
        ((self.total_agents as f64) * self.consensus_threshold).ceil() as usize
    }

    pub fn required_for_bft(&self) -> usize {
        // BFT requires 2/3 + 1 consensus
        ((2 * self.total_agents) as f64 / 3.0).floor() as usize + 1
    }

    pub fn max_tolerated_failures(&self) -> usize {
        (self.total_agents - 1) / 3
    }

    pub fn is_quorum_reached(&self, commits: usize) -> bool {
        commits >= self.required_commits()
    }

    pub fn is_bft_quorum_reached(&self, commits: usize) -> bool {
        commits >= self.required_for_bft()
    }

    pub fn can_tolerate_failures(&self, failures: usize) -> Result<bool, BftConsensusError> {
        let max_failures = self.max_tolerated_failures();
        if failures > max_failures {
            return Err(BftConsensusError::MaxFailuresExceeded(format!(
                "Failures ({}) exceed BFT tolerance ({})",
                failures, max_failures
            )));
        }
        Ok(true)
    }

    pub fn total_agents(&self) -> usize {
        self.total_agents
    }

    pub fn consensus_threshold(&self) -> f64 {
        self.consensus_threshold
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bft_tolerance_3_agents() {
        let q = QuorumValidator::new(3, 2.0 / 3.0).unwrap();
        assert_eq!(q.max_tolerated_failures(), 0);
    }

    #[test]
    fn test_bft_tolerance_4_agents() {
        let q = QuorumValidator::new(4, 2.0 / 3.0).unwrap();
        assert_eq!(q.max_tolerated_failures(), 1);
    }

    #[test]
    fn test_bft_tolerance_7_agents() {
        let q = QuorumValidator::new(7, 2.0 / 3.0).unwrap();
        assert_eq!(q.max_tolerated_failures(), 2);
    }
}

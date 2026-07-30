pub mod region_down;
pub mod network_partition;
pub mod split_brain_cross_region;

pub use region_down::{RegionDownScenario, RegionFailoverResult};
pub use network_partition::{NetworkPartitionScenario, PartitionDetectionResult};
pub use split_brain_cross_region::{SplitBrainScenario, SplitBrainResolutionResult};

pub mod network_partition;
pub mod region_down;
pub mod split_brain_cross_region;

pub use network_partition::{NetworkPartitionScenario, PartitionDetectionResult};
pub use region_down::{RegionDownScenario, RegionFailoverResult};
pub use split_brain_cross_region::{SplitBrainResolutionResult, SplitBrainScenario};

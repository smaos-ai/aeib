/// EDEN Cluster: Mission modules for humanitarian/conflict-zone scenarios.
pub mod eden;
pub mod witness;

pub use eden::{
    FamilyCommandCenterCapsule, FamilyUnit, FamilyMember, FamilyRole, AgeGroup,
    EducationCapsule, StudentRecord, LearningProgress, Curriculum, CurriculumModule,
    Lesson, Exercise, AssessmentMethod, HouseholdDecisions, EnergyDecision,
    FoodSovereignty, Seed, RecipeFromHarvest, FinancialDecision, LocalProjectVote,
    VoteChoice, RegenerationFundGovernance, RegenerationProject, ProjectCategory,
    ProjectStatus, ImpactMetrics, PrivacyLevel,
};
pub use witness::{DigitalWitnessCapsule, WitnessContent, WitnessGenerationError};

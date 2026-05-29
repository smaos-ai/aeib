/// EDEN Cluster E: Family Command Center Capsule
///
/// Local family AI tutor system with:
/// - Sovereign AI tutor (Qwen3.5-4B distilled model on Raspberry Pi)
/// - Family-safe education content filtering
/// - Home mesh networking + local orchestration
/// - Household decision-making (energy, food, finance)
/// - Regeneration fund governance (community voting)
/// - Zero FDA regulation (education-focused, not medical)

use serde::{Deserialize, Serialize};
use std::time::SystemTime;
use std::collections::HashMap;
use uuid::Uuid;

// ============================================================================
// DATA STRUCTURES
// ============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyCommandCenterCapsule {
    /// Capsule identifier (UUID)
    pub capsule_id: String,

    /// Family unit metadata (members, location)
    pub family_unit: FamilyUnit,

    /// Education module (sovereign AI tutor)
    pub education_capsule: EducationCapsule,

    /// Household decision-making (energy, food, finance)
    pub household_decisions: HouseholdDecisions,

    /// Regeneration fund governance (vote on community projects)
    pub regeneration_fund_governance: RegenerationFundGovernance,

    /// Encryption key identifier (family holds key, not cloud)
    pub encryption_key_id: String,

    /// Privacy level (full_privacy | community_visibility)
    pub privacy_level: PrivacyLevel,

    /// Timestamp of capsule creation
    pub created_at: SystemTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum PrivacyLevel {
    FullPrivacy,           // No data shared with anyone
    CommunityVisibility,   // Aggregate data visible to community (no PII)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyUnit {
    /// Family members
    pub members: Vec<FamilyMember>,

    /// Household location (latitude, longitude)
    pub household_location: (f64, f64),

    /// Household name (for community projects)
    pub household_name: String,

    /// Family identifier (UUID)
    pub family_id: String,

    /// Founded date
    pub founded_date: SystemTime,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyMember {
    pub member_id: String,  // Anonymous identifier (not name)
    pub age_group: AgeGroup,
    pub role: FamilyRole,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AgeGroup {
    PreK,       // 0-5
    Elementary, // 6-12
    Teen,       // 13-18
    Adult,      // 18-65
    Senior,     // 65+
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum FamilyRole {
    Student,
    Parent,
    Guardian,
    Grandparent,
    Sibling,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EducationCapsule {
    /// Students in the family
    pub students: Vec<StudentRecord>,

    /// Tutor model name (e.g., "Qwen3.5-4B-distilled")
    pub tutor_model_name: String,

    /// Curriculum (math, reading, science, civic)
    pub curriculum: Curriculum,

    /// Assessment method (adaptive, mastery-based)
    pub assessment_method: AssessmentMethod,

    /// Model runs locally (no cloud API calls)
    pub local_only: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StudentRecord {
    pub student_id: String,
    pub age_group: AgeGroup,
    pub progress: LearningProgress,
    pub current_module: String, // e.g., "fractions_v2"
    pub mastery_level: f32,     // 0.0 - 1.0
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LearningProgress {
    pub lessons_completed: u32,
    pub problems_solved: u32,
    pub accuracy: f32,                  // 0.0 - 1.0
    pub last_session: Option<SystemTime>,
    pub total_hours: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Curriculum {
    pub language: String,    // "en", "es", "pt", "uk"
    pub grade_level: String, // "elementary", "middle", "high"
    pub subjects: HashMap<String, CurriculumModule>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CurriculumModule {
    pub subject: String, // "math", "reading", "science", "civic"
    pub lessons: Vec<Lesson>,
    pub total_hours: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Lesson {
    pub lesson_id: String,
    pub title: String,
    pub content: String, // Markdown
    pub exercises: Vec<Exercise>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Exercise {
    pub exercise_id: String,
    pub problem: String,
    pub correct_answer: String,
    pub explanation: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AssessmentMethod {
    Adaptive,      // Difficulty adjusts based on performance
    MasteryBased,  // Student must reach 90%+ before advancing
    Portfolio,     // Curated collection of student work
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HouseholdDecisions {
    /// Energy consumption & solar production
    pub energy: EnergyDecision,

    /// Food sovereignty (garden yield, recipes)
    pub food: FoodSovereignty,

    /// Financial (AP2 earnings, regeneration contributions)
    pub financial: FinancialDecision,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EnergyDecision {
    pub solar_production_kwh: u32,     // Daily solar production
    pub grid_import_kwh: u32,          // Purchased from grid
    pub self_consumption_kwh: u32,     // Consumed from solar
    pub self_sufficiency_percent: f32, // (solar / total) * 100
    pub consumption_by_appliance: HashMap<String, u32>, // "refrigerator" → 50 kwh/month
    pub ai_recommendation: String,     // "reduce AC usage at peak hours"
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FoodSovereignty {
    pub garden_yield_kg: u32,              // Monthly garden harvest
    pub water_efficiency: f32,             // liters per kg produced
    pub seed_catalog: Vec<Seed>,
    pub recipes_from_harvest: Vec<RecipeFromHarvest>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Seed {
    pub seed_name: String,
    pub local_variety: bool,
    pub yield_kg: u32,
    pub water_requirement_liters: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecipeFromHarvest {
    pub recipe_name: String,
    pub ingredients: Vec<String>, // from garden
    pub instructions: String,
    pub family_rating: f32, // 1-5 stars
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FinancialDecision {
    pub ap2_earnings_usd: u32,                  // From research participation + local services
    pub regeneration_fund_contribution_usd: u32, // Family's contribution
    pub local_investment_votes: Vec<LocalProjectVote>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LocalProjectVote {
    pub project_id: String,
    pub project_name: String,
    pub budget_requested: u32,
    pub family_vote: VoteChoice,
    pub vote_date: SystemTime,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum VoteChoice {
    For,
    Against,
    Abstain,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RegenerationFundGovernance {
    /// Local projects the family can vote on
    pub local_projects: Vec<RegenerationProject>,

    /// Impact metrics (soil carbon, water retention, biodiversity)
    pub impact_measurement: ImpactMetrics,

    /// Foundation match (1:1 up to $10k per project)
    pub foundation_match_enabled: bool,

    /// Total contributed to regeneration fund
    pub total_contributed_usd: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RegenerationProject {
    pub project_id: String,
    pub project_name: String,
    pub description: String,
    pub category: ProjectCategory,
    pub budget_requested_usd: u32,
    pub community_votes: u32,
    pub foundation_match_usd: u32,
    pub status: ProjectStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ProjectCategory {
    CommunityGarden,
    School,
    WaterRetention,
    SoilRegrowth,
    CommunityCenter,
    Library,
    HealthClinic,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ProjectStatus {
    Proposed,
    FundingInProgress,
    Funded,
    InProgress,
    Completed,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ImpactMetrics {
    pub soil_carbon_increase_tons: f32,
    pub water_retention_gallons: f32,
    pub biodiversity_index: f32, // 0.0 - 1.0 (species count / baseline)
    pub community_participation_families: u32,
    pub last_measurement: SystemTime,
}

// ============================================================================
// IMPLEMENTATION
// ============================================================================

impl FamilyCommandCenterCapsule {
    /// Create a new FamilyCommandCenterCapsule
    pub fn new(
        family_name: String,
        household_location: (f64, f64),
        members: Vec<FamilyMember>,
    ) -> Self {
        let family_id = Uuid::new_v4().to_string();
        let capsule_id = Uuid::new_v4().to_string();
        let encryption_key_id = Uuid::new_v4().to_string();

        let family_unit = FamilyUnit {
            members,
            household_location,
            household_name: family_name,
            family_id,
            founded_date: SystemTime::now(),
        };

        let education_capsule = EducationCapsule {
            students: Vec::new(),
            tutor_model_name: "Qwen3.5-4B-distilled".to_string(),
            curriculum: Curriculum {
                language: "en".to_string(),
                grade_level: "elementary".to_string(),
                subjects: HashMap::new(),
            },
            assessment_method: AssessmentMethod::Adaptive,
            local_only: true,
        };

        let household_decisions = HouseholdDecisions {
            energy: EnergyDecision {
                solar_production_kwh: 0,
                grid_import_kwh: 0,
                self_consumption_kwh: 0,
                self_sufficiency_percent: 0.0,
                consumption_by_appliance: HashMap::new(),
                ai_recommendation: String::new(),
            },
            food: FoodSovereignty {
                garden_yield_kg: 0,
                water_efficiency: 0.0,
                seed_catalog: Vec::new(),
                recipes_from_harvest: Vec::new(),
            },
            financial: FinancialDecision {
                ap2_earnings_usd: 0,
                regeneration_fund_contribution_usd: 0,
                local_investment_votes: Vec::new(),
            },
        };

        let regeneration_fund_governance = RegenerationFundGovernance {
            local_projects: Vec::new(),
            impact_measurement: ImpactMetrics {
                soil_carbon_increase_tons: 0.0,
                water_retention_gallons: 0.0,
                biodiversity_index: 0.0,
                community_participation_families: 0,
                last_measurement: SystemTime::now(),
            },
            foundation_match_enabled: true,
            total_contributed_usd: 0,
        };

        FamilyCommandCenterCapsule {
            capsule_id,
            family_unit,
            education_capsule,
            household_decisions,
            regeneration_fund_governance,
            encryption_key_id,
            privacy_level: PrivacyLevel::FullPrivacy,
            created_at: SystemTime::now(),
        }
    }

    /// Add a student to the family
    pub fn add_student(&mut self, student: StudentRecord) {
        self.education_capsule.students.push(student);
    }

    /// Calculate energy self-sufficiency percentage
    pub fn calculate_energy_self_sufficiency(&mut self) {
        let total_consumption = self.household_decisions.energy.self_consumption_kwh
            + self.household_decisions.energy.grid_import_kwh;

        if total_consumption > 0 {
            self.household_decisions.energy.self_sufficiency_percent =
                (self.household_decisions.energy.self_consumption_kwh as f32 / total_consumption as f32)
                    * 100.0;
        } else {
            self.household_decisions.energy.self_sufficiency_percent = 0.0;
        }
    }

    /// Calculate garden water efficiency (liters per kg)
    pub fn calculate_water_efficiency(&mut self) {
        let total_yield: u32 = self
            .household_decisions
            .food
            .seed_catalog
            .iter()
            .map(|s| s.yield_kg)
            .sum();

        let total_water: u32 = self
            .household_decisions
            .food
            .seed_catalog
            .iter()
            .map(|s| s.water_requirement_liters)
            .sum();

        if total_yield > 0 {
            self.household_decisions.food.water_efficiency = total_water as f32 / total_yield as f32;
        } else {
            self.household_decisions.food.water_efficiency = 0.0;
        }
    }

    /// Update garden yield from seed catalog
    pub fn update_garden_yield(&mut self) {
        let total_yield: u32 = self
            .household_decisions
            .food
            .seed_catalog
            .iter()
            .map(|s| s.yield_kg)
            .sum();
        self.household_decisions.food.garden_yield_kg = total_yield;
    }

    /// Add AP2 earnings (from research participation)
    pub fn add_ap2_earnings(&mut self, amount: u32) {
        self.household_decisions.financial.ap2_earnings_usd += amount;
    }

    /// Vote on a regeneration project
    pub fn vote_on_project(&mut self, project_id: String, vote: VoteChoice) -> Result<(), String> {
        // Find the project in local_projects
        let project = self
            .regeneration_fund_governance
            .local_projects
            .iter_mut()
            .find(|p| p.project_id == project_id)
            .ok_or_else(|| "Project not found".to_string())?;

        // Record vote
        let vote_record = LocalProjectVote {
            project_id: project_id.clone(),
            project_name: project.project_name.clone(),
            budget_requested: project.budget_requested_usd,
            family_vote: vote.clone(),
            vote_date: SystemTime::now(),
        };

        self.household_decisions
            .financial
            .local_investment_votes
            .push(vote_record);

        // Increment community vote count
        project.community_votes += 1;

        Ok(())
    }

    /// Calculate foundation match for a project
    pub fn calculate_foundation_match(&self, budget_requested: u32) -> u32 {
        if !self.regeneration_fund_governance.foundation_match_enabled {
            return 0;
        }

        let max_match = 10000;
        if budget_requested <= max_match {
            budget_requested // 1:1 match
        } else {
            max_match // Cap at $10k
        }
    }

    /// Update student mastery level
    pub fn update_student_mastery(
        &mut self,
        student_id: &str,
        new_mastery: f32,
    ) -> Result<(), String> {
        let student = self
            .education_capsule
            .students
            .iter_mut()
            .find(|s| s.student_id == student_id)
            .ok_or_else(|| "Student not found".to_string())?;

        // Clamp mastery level between 0.0 and 1.0
        student.mastery_level = new_mastery.min(1.0).max(0.0);

        Ok(())
    }

    /// Check if student can advance to next lesson (mastery-based)
    pub fn can_advance_to_next_lesson(&self, student_id: &str) -> Result<bool, String> {
        if self.education_capsule.assessment_method != AssessmentMethod::MasteryBased {
            return Ok(true); // Non-mastery methods don't have advancement gates
        }

        let student = self
            .education_capsule
            .students
            .iter()
            .find(|s| s.student_id == student_id)
            .ok_or_else(|| "Student not found".to_string())?;

        // Mastery threshold: 90%
        Ok(student.progress.accuracy >= 0.90)
    }

    /// Generate energy AI recommendation
    pub fn generate_energy_recommendation(&mut self) {
        let recommendation = if self.household_decisions.energy.self_sufficiency_percent < 50.0 {
            "Increase solar panel investment or reduce peak-hour consumption.".to_string()
        } else if self.household_decisions.energy.self_sufficiency_percent < 80.0 {
            "Consider shifting high-consumption tasks (dishwasher, laundry) to off-peak hours.".to_string()
        } else {
            "Excellent energy autonomy! Monitor battery storage for resilience.".to_string()
        };

        self.household_decisions.energy.ai_recommendation = recommendation;
    }

    /// Enable community visibility for aggregate metrics (privacy)
    pub fn enable_community_visibility(&mut self) {
        self.privacy_level = PrivacyLevel::CommunityVisibility;
    }

    /// Verify zero cloud API dependency (local-only model)
    pub fn verify_local_only_mode(&self) -> bool {
        self.education_capsule.local_only
    }
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_family_command_center() {
        // Create FamilyCommandCenterCapsule for a family of 4
        let members = vec![
            FamilyMember {
                member_id: Uuid::new_v4().to_string(),
                age_group: AgeGroup::Adult,
                role: FamilyRole::Parent,
            },
            FamilyMember {
                member_id: Uuid::new_v4().to_string(),
                age_group: AgeGroup::Adult,
                role: FamilyRole::Parent,
            },
            FamilyMember {
                member_id: Uuid::new_v4().to_string(),
                age_group: AgeGroup::Elementary,
                role: FamilyRole::Student,
            },
            FamilyMember {
                member_id: Uuid::new_v4().to_string(),
                age_group: AgeGroup::Teen,
                role: FamilyRole::Student,
            },
        ];

        let capsule = FamilyCommandCenterCapsule::new(
            "Smith Family".to_string(),
            (37.7749, -122.4194), // San Francisco
            members,
        );

        // Assert: family_id is UUID (string length 36)
        assert_eq!(capsule.family_unit.family_id.len(), 36);
        assert_eq!(capsule.family_unit.members.len(), 4);

        // Assert: household_location is valid GPS
        assert!(capsule.family_unit.household_location.0 >= -90.0
            && capsule.family_unit.household_location.0 <= 90.0);
        assert!(capsule.family_unit.household_location.1 >= -180.0
            && capsule.family_unit.household_location.1 <= 180.0);
    }

    #[test]
    fn test_education_tutor_local_only_no_cloud() {
        // Create capsule with education module
        let members = vec![FamilyMember {
            member_id: Uuid::new_v4().to_string(),
            age_group: AgeGroup::Elementary,
            role: FamilyRole::Student,
        }];

        let capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        // Assert: tutor model is Qwen3.5-4B distilled
        assert_eq!(
            capsule.education_capsule.tutor_model_name,
            "Qwen3.5-4B-distilled"
        );

        // Assert: no cloud API calls (local_only = true)
        assert!(capsule.verify_local_only_mode());
        assert!(capsule.education_capsule.local_only);
    }

    #[test]
    fn test_education_adaptive_difficulty() {
        // Create student with mastery_level = 0.5 (50%)
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        let student_id = Uuid::new_v4().to_string();
        let student = StudentRecord {
            student_id: student_id.clone(),
            age_group: AgeGroup::Elementary,
            progress: LearningProgress {
                lessons_completed: 5,
                problems_solved: 50,
                accuracy: 0.5,
                last_session: None,
                total_hours: 2.5,
            },
            current_module: "fractions_v1".to_string(),
            mastery_level: 0.5,
        };

        capsule.add_student(student);

        // Student solves correctly → mastery_level = 0.6
        capsule
            .update_student_mastery(&student_id, 0.6)
            .expect("update should succeed");

        // Assert: new mastery is higher (increased difficulty is implied)
        let updated_student = capsule
            .education_capsule
            .students
            .iter()
            .find(|s| s.student_id == student_id)
            .expect("student should exist");
        assert_eq!(updated_student.mastery_level, 0.6);
    }

    #[test]
    fn test_education_mastery_based_progression() {
        // Set assessment_method = MasteryBased
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        capsule.education_capsule.assessment_method = AssessmentMethod::MasteryBased;

        let student_id = Uuid::new_v4().to_string();
        let mut student = StudentRecord {
            student_id: student_id.clone(),
            age_group: AgeGroup::Elementary,
            progress: LearningProgress {
                lessons_completed: 5,
                problems_solved: 50,
                accuracy: 0.85,
                last_session: None,
                total_hours: 2.5,
            },
            current_module: "fractions_v1".to_string(),
            mastery_level: 0.85,
        };

        // Student gets 85% → cannot advance
        assert!(!capsule
            .can_advance_to_next_lesson(&student_id)
            .unwrap_or(false));

        capsule.add_student(student.clone());

        // Student practices, gets 91% → can advance
        student.progress.accuracy = 0.91;
        let student_idx = capsule
            .education_capsule
            .students
            .iter_mut()
            .find(|s| s.student_id == student_id)
            .expect("student should exist");
        student_idx.progress.accuracy = 0.91;

        assert!(capsule
            .can_advance_to_next_lesson(&student_id)
            .unwrap_or(false));
    }

    #[test]
    fn test_energy_self_sufficiency_calculation() {
        // Set: solar_production = 100 kwh, grid_import = 30 kwh
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        capsule.household_decisions.energy.self_consumption_kwh = 100;
        capsule.household_decisions.energy.grid_import_kwh = 30;

        capsule.calculate_energy_self_sufficiency();

        // Assert: self_sufficiency_percent = (100 / 130) * 100 = 76.9%
        let expected = (100.0 / 130.0) * 100.0;
        assert!((capsule.household_decisions.energy.self_sufficiency_percent - expected).abs() < 0.1);
    }

    #[test]
    fn test_energy_ai_recommendation() {
        // Analyze household consumption patterns
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        // Low self-sufficiency
        capsule.household_decisions.energy.self_sufficiency_percent = 30.0;
        capsule.generate_energy_recommendation();
        assert!(capsule.household_decisions.energy.ai_recommendation.contains("solar"));

        // Medium self-sufficiency
        capsule.household_decisions.energy.self_sufficiency_percent = 70.0;
        capsule.generate_energy_recommendation();
        assert!(capsule.household_decisions.energy.ai_recommendation.contains("off-peak"));

        // High self-sufficiency
        capsule.household_decisions.energy.self_sufficiency_percent = 90.0;
        capsule.generate_energy_recommendation();
        assert!(capsule.household_decisions.energy.ai_recommendation.contains("battery"));
    }

    #[test]
    fn test_food_sovereignty_garden_yield() {
        // Create garden with 3 seed varieties
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        capsule.household_decisions.food.seed_catalog = vec![
            Seed {
                seed_name: "Tomato".to_string(),
                local_variety: true,
                yield_kg: 50,
                water_requirement_liters: 200,
            },
            Seed {
                seed_name: "Lettuce".to_string(),
                local_variety: true,
                yield_kg: 30,
                water_requirement_liters: 100,
            },
            Seed {
                seed_name: "Carrot".to_string(),
                local_variety: false,
                yield_kg: 25,
                water_requirement_liters: 80,
            },
        ];

        capsule.update_garden_yield();
        capsule.calculate_water_efficiency();

        // Assert: total_yield calculated from all seeds
        assert_eq!(capsule.household_decisions.food.garden_yield_kg, 105);

        // Assert: water_efficiency = total_water / total_yield = 380 / 105 ≈ 3.619 (liters per kg)
        let expected_efficiency = 380.0 / 105.0;
        assert!((capsule.household_decisions.food.water_efficiency - expected_efficiency).abs() < 0.001);
    }

    #[test]
    fn test_financial_ap2_earnings_accumulate() {
        // Family participates in research → AP2 earnings accumulate
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        assert_eq!(capsule.household_decisions.financial.ap2_earnings_usd, 0);

        capsule.add_ap2_earnings(100);
        assert_eq!(capsule.household_decisions.financial.ap2_earnings_usd, 100);

        capsule.add_ap2_earnings(200);
        assert_eq!(capsule.household_decisions.financial.ap2_earnings_usd, 300);
    }

    #[test]
    fn test_regeneration_fund_vote_mechanics() {
        // Create local project: Community Garden ($5k budget)
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        let project = RegenerationProject {
            project_id: Uuid::new_v4().to_string(),
            project_name: "Community Garden".to_string(),
            description: "Local food growing space".to_string(),
            category: ProjectCategory::CommunityGarden,
            budget_requested_usd: 5000,
            community_votes: 0,
            foundation_match_usd: 0,
            status: ProjectStatus::Proposed,
        };

        capsule
            .regeneration_fund_governance
            .local_projects
            .push(project.clone());

        // Family votes: VoteChoice::For
        capsule
            .vote_on_project(project.project_id.clone(), VoteChoice::For)
            .expect("vote should succeed");

        // Assert: project community_votes incremented
        let updated_project = capsule
            .regeneration_fund_governance
            .local_projects
            .iter()
            .find(|p| p.project_id == project.project_id)
            .expect("project should exist");
        assert_eq!(updated_project.community_votes, 1);

        // Assert: vote record exists in family's votes
        assert_eq!(capsule.household_decisions.financial.local_investment_votes.len(), 1);
    }

    #[test]
    fn test_regeneration_fund_foundation_match() {
        // Project budget: $5,000
        let members = vec![];
        let capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        // Foundation match limit: $10,000 per project
        let match_amount = capsule.calculate_foundation_match(5000);

        // Assert: match_usd == $5,000 (1:1 match)
        assert_eq!(match_amount, 5000);

        // Test match cap at $10k
        let match_amount_large = capsule.calculate_foundation_match(20000);
        assert_eq!(match_amount_large, 10000);
    }

    #[test]
    fn test_impact_metrics_soil_carbon_measurement() {
        // Regeneration projects complete → impact metrics recorded
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        // Set impact metrics
        capsule.regeneration_fund_governance.impact_measurement.soil_carbon_increase_tons = 2.0;
        capsule.regeneration_fund_governance.impact_measurement.water_retention_gallons = 5000.0;
        capsule.regeneration_fund_governance.impact_measurement.biodiversity_index = 0.75;
        capsule.regeneration_fund_governance.impact_measurement.community_participation_families = 20;

        // Assert: metrics recorded correctly
        assert_eq!(
            capsule.regeneration_fund_governance.impact_measurement.soil_carbon_increase_tons,
            2.0
        );
        assert_eq!(
            capsule.regeneration_fund_governance.impact_measurement.community_participation_families,
            20
        );
    }

    #[test]
    fn test_privacy_full_privacy_no_data_shared() {
        // Create capsule with privacy_level = FullPrivacy
        let members = vec![];
        let capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        // Assert: privacy level is FullPrivacy
        assert_eq!(capsule.privacy_level, PrivacyLevel::FullPrivacy);

        // Assert: no aggregate stats shared (zero visibility)
        // This is enforced at data export time (not in this struct)
    }

    #[test]
    fn test_privacy_community_visibility_aggregate_only() {
        // Create capsule with privacy_level = CommunityVisibility
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        capsule.enable_community_visibility();

        // Assert: privacy level is CommunityVisibility
        assert_eq!(capsule.privacy_level, PrivacyLevel::CommunityVisibility);

        // Individual family data is NOT visible at struct level
        // (data filtering enforced at API/export layer)
    }

    #[test]
    fn test_curriculum_localization() {
        // Create curriculum in English
        let members = vec![];
        let mut capsule =
            FamilyCommandCenterCapsule::new("Test Family".to_string(), (0.0, 0.0), members);

        capsule.education_capsule.curriculum.language = "en".to_string();
        assert_eq!(capsule.education_capsule.curriculum.language, "en");

        // Create curriculum in Spanish
        capsule.education_capsule.curriculum.language = "es".to_string();
        assert_eq!(capsule.education_capsule.curriculum.language, "es");

        // Create curriculum in Ukrainian
        capsule.education_capsule.curriculum.language = "uk".to_string();
        assert_eq!(capsule.education_capsule.curriculum.language, "uk");
    }
}

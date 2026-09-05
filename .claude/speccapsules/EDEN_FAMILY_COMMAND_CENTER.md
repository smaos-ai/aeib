# SPECCAPSULE: Eden Garden 2.0 Family Command Center
## Spec-First Design for FamilyCommandCenterCapsule

**Created:** May 29, 2026 | **Target Implementation:** June 4-14, 2026  
**Crate:** `crates/siss-agent-shell` (new module: `family_command_center.rs`)  
**Tests:** TDD-first | **Integration:** Schools, community gardens, cooperative networks

---

## STRUCT DEFINITION

```rust
use crate::capsule::Capsule;
use crate::oracle_distillation::OracleDistillationModel; // Layer 14
use serde::{Deserialize, Serialize};
use std::time::SystemTime;
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyCommandCenterCapsule {
    /// Core Capsule wrapper
    pub capsule: Capsule,
    
    /// Family unit metadata (members, location)
    pub family_unit: FamilyUnit,
    
    /// Education module (sovereign AI tutor)
    pub education_capsule: EducationCapsule,
    
    /// Household decision-making (energy, food, finance)
    pub household_decisions: HouseholdDecisions,
    
    /// Regeneration fund governance (vote on community projects)
    pub regeneration_fund_governance: RegenerationFundGovernance,
    
    /// Encryption (AES-256-GCM-SIV, family holds key)
    pub encryption_key_id: String,
    
    /// Privacy level (full_privacy | community_visibility)
    pub privacy_level: PrivacyLevel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum PrivacyLevel {
    FullPrivacy, // No data shared with anyone
    CommunityVisibility, // Aggregate data visible to community (no PII)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyUnit {
    /// Family members
    pub members: Vec<FamilyMember>,
    
    /// Household location
    pub household_location: (f64, f64), // (latitude, longitude)
    
    /// Household name (for community projects)
    pub household_name: String,
    
    /// Family identifier (UUID)
    pub family_id: String,
    
    /// Founded date
    pub founded_date: SystemTime,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FamilyMember {
    pub member_id: String, // Anonymous identifier (not name)
    pub age_group: AgeGroup, // 0-5, 6-12, 13-18, 18-65, 65+
    pub role: FamilyRole,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AgeGroup {
    PreK,      // 0-5
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
    
    /// Sovereign AI tutor (runs on Raspberry Pi, no cloud)
    pub tutor_model: OracleDistillationModel,
    
    /// Curriculum (math, reading, science, civic)
    pub curriculum: Curriculum,
    
    /// Assessment method (adaptive, mastery-based)
    pub assessment_method: AssessmentMethod,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StudentRecord {
    pub student_id: String,
    pub age_group: AgeGroup,
    pub progress: LearningProgress,
    pub current_module: String, // "fractions_v2", "photosynthesis_v1", etc.
    pub mastery_level: f32, // 0.0 - 1.0
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LearningProgress {
    pub lessons_completed: u32,
    pub problems_solved: u32,
    pub accuracy: f32, // 0.0 - 1.0
    pub last_session: Option<SystemTime>,
    pub total_hours: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Curriculum {
    pub language: String, // "en", "es", "pt", "uk"
    pub grade_level: String, // "elementary", "middle", "high", "college"
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
    Adaptive, // Difficulty adjusts based on performance
    MasteryBased, // Student must reach 90%+ before advancing
    Portfolio, // Curated collection of student work
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
    pub solar_production_kwh: u32, // Daily solar production
    pub grid_import_kwh: u32, // Purchased from grid
    pub self_consumption_kwh: u32, // Consumed from solar
    pub self_sufficiency_percent: f32, // (solar / total) * 100
    pub consumption_by_appliance: HashMap<String, u32>, // "refrigerator" → 50 kwh/month
    pub ai_recommendation: String, // "reduce AC usage at peak hours"
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FoodSovereignty {
    pub garden_yield_kg: u32, // Monthly garden harvest
    pub water_efficiency: f32, // liters per kg produced
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
    pub ap2_earnings_usd: u32, // From research participation + local services
    pub regeneration_fund_contribution_usd: u32, // Family's 1% contribution
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
```

---

## TEST CASES (TDD Template)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_family_command_center() {
        // Create FamilyCommandCenterCapsule for a family of 4
        // Assert: family_id is UUID
        // Assert: household_location is valid GPS
    }

    #[tokio::test]
    async fn test_education_tutor_runs_locally_on_raspberry_pi() {
        // Create capsule with education module
        // Load Qwen3.5-4B distilled model
        // Run inference on Raspberry Pi (CPU-only)
        // Assert: inference <500ms
        // Assert: no cloud API calls made (zero privacy leakage)
    }

    #[tokio::test]
    async fn test_education_adaptive_difficulty() {
        // Create student with mastery_level = 0.5 (50%)
        // Tutor presents problem
        // Student solves correctly → mastery_level = 0.6
        // Tutor increases difficulty
        // Assert: new problem is harder
    }

    #[tokio::test]
    async fn test_education_mastery_based_progression() {
        // Set assessment_method = MasteryBased
        // Student must reach 90%+ accuracy
        // Student gets 85% → cannot advance
        // Student practices, gets 91% → can advance
        // Assert: progression is blocked until mastery
    }

    #[tokio::test]
    async fn test_energy_self_sufficiency_calculation() {
        // Set: solar_production = 100 kwh, grid_import = 30 kwh
        // Calculate: self_sufficiency_percent = (100 / 130) * 100 = 76.9%
        // Assert: calculation correct
    }

    #[tokio::test]
    async fn test_energy_ai_recommendation() {
        // Analyze household consumption patterns
        // Peak hours: 18:00-21:00 (refrigerator + AC)
        // Off-peak: 02:00-06:00 (minimal usage)
        // AI recommends: "shift dishwasher to 02:00-06:00"
        // Assert: recommendation reduces peak load
    }

    #[tokio::test]
    async fn test_food_sovereignty_garden_yield() {
        // Create garden with 3 seed varieties
        // Each seed has yield_kg + water_requirement_liters
        // Assert: total_yield calculated from all seeds
        // Assert: water_efficiency = total_yield / total_water
    }

    #[tokio::test]
    async fn test_financial_ap2_earnings_accumulate() {
        // Family participates in diabetes research (biometric data)
        // Commercial value from research: $10k
        // Family's royalty (1%): $100
        // Assert: ap2_earnings_usd incremented
    }

    #[tokio::test]
    async fn test_regeneration_fund_vote_mechanics() {
        // Create local project: Community Garden ($5k budget)
        // Family votes: VoteChoice::For
        // Other 19 families also vote
        // Project wins (60% approval)
        // Foundation match: $5k
        // Total budget: $5k + $5k match = $10k
        // Assert: project status = Funded
    }

    #[tokio::test]
    async fn test_regeneration_fund_foundation_match() {
        // Project budget: $5,000
        // Foundation match limit: $10,000 per project
        // Foundation match: $5,000 (1:1 match, up to limit)
        // Total available: $10,000
        // Assert: match_usd == $5,000
    }

    #[tokio::test]
    async fn test_impact_metrics_soil_carbon_measurement() {
        // Regeneration projects complete over 6 months
        // Baseline soil carbon: 10 tons/hectare
        // After projects: 12 tons/hectare
        // Increase: 2 tons/hectare
        // Assert: soil_carbon_increase_tons == 2.0
    }

    #[tokio::test]
    async fn test_privacy_full_privacy_no_data_shared() {
        // Create capsule with privacy_level = FullPrivacy
        // Assert: no data visible to community
        // Assert: no aggregate stats shared
    }

    #[tokio::test]
    async fn test_privacy_community_visibility_aggregate_only() {
        // Create capsule with privacy_level = CommunityVisibility
        // Aggregate metrics available: "20 families participating"
        // Individual family data: NOT visible (PII removed)
        // Assert: zero reidentification risk
    }

    #[tokio::test]
    async fn test_curriculum_localization() {
        // Create curriculum in Spanish ("es")
        // All lessons + exercises in Spanish
        // Create curriculum in Ukrainian ("uk")
        // All lessons + exercises in Ukrainian
        // Assert: each language fully supported
    }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Family Unit + Education (June 4-6)
- [ ] Implement `FamilyCommandCenterCapsule::new()` — create family unit
- [ ] Implement `EducationCapsule::new()` — load sovereign AI tutor on Raspberry Pi
- [ ] Implement student progress tracking (mastery_level, lessons_completed)
- [ ] All unit tests pass

### Phase 2: AI Tutor Integration (June 7-9)
- [ ] Integrate `crates/siss-graph-db::oracle_distillation` (Qwen3.5-4B distilled from Claude)
- [ ] Implement adaptive difficulty adjustment based on performance
- [ ] Implement mastery-based progression (90%+ required)
- [ ] Benchmark: tutor inference <500ms on Raspberry Pi (CPU-only)
- [ ] Verify: zero cloud API calls (privacy 100%)

### Phase 3: Energy + Food + Finance (June 10-12)
- [ ] Implement `HouseholdDecisions::calculate_self_sufficiency()` — energy autonomy
- [ ] Implement `HouseholdDecisions::recommend_energy_optimization()` — AI suggestions
- [ ] Implement `FoodSovereignty::calculate_yield()` — garden metrics
- [ ] Implement `FinancialDecision::track_ap2_earnings()` — research royalties
- [ ] Integration tests with mock energy meter + garden sensors

### Phase 4: Regeneration Fund + Launch (June 13-14)
- [ ] Implement `RegenerationFundGovernance::vote_on_project()` — family voting
- [ ] Implement Foundation 1:1 match calculation
- [ ] Implement impact metrics calculation (soil carbon, water, biodiversity)
- [ ] Integration tests with mock community projects
- [ ] All tests green: `cargo test -p siss-agent-shell`

---

## INTEGRATION POINTS

### Existing Crates Used
- **siss-graph-db:** Capsule, oracle_distillation (Qwen3.5-4B tutor model)
- **siss-night-cycle:** MemForest for efficient educational progress compression
- **siss-context-cartography:** Geo-spatial analysis for local regeneration projects
- **siss-tools:** AES-256-GCM-SIV encryption for family privacy

### Partner APIs
- **Energy Utilities:** Read smart meter data (solar production, grid import)
- **Local Schools:** Curriculum standards alignment
- **Community Gardens:** Seed inventory, harvest yield reporting
- **Local Government:** Project registry, community voting platform

---

## SUCCESS CRITERIA (Must Pass Before December 31)

- [ ] 5,000+ active FamilyCommandCenterCapsules
- [ ] 15,000+ students using sovereign AI tutors (on Raspberry Pi)
- [ ] 30%+ improvement in mastery-based learning outcomes (vs. traditional schools)
- [ ] $500K in Regeneration Fund distributed to community projects
- [ ] 200 local projects funded (gardens, schools, community centers)
- [ ] 50,000+ acres of land improved (carbon + water + biodiversity)
- [ ] Zero corporate data harvesting in any family system
- [ ] 100% family data encryption (AES-256-GCM-SIV)

---

## FILES TO CREATE

```
crates/siss-agent-shell/src/
└── family_command_center.rs (estimated 500-600 LOC)

crates/siss-agent-shell/tests/
└── family_command_center_test.rs (estimated 300-400 LOC)

docs/curriculum/
├── math_elementary_en.md
├── reading_elementary_es.md
├── science_middle_uk.md
└── civic_high_all_langs.md (starter templates)
```

---

## OWNER & DEADLINE

**Owner:** Agent-Cluster-E (Parallel Implementation Team)  
**Target Completion:** June 14, 2026  
**Launch Date:** September 1, 2026 (Live PoC with 5,000 families)

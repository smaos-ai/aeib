# STREAM 3: Capsule Ecosystem Specification
**Status:** LOCKED (Constitutional)  
**Date:** July 18, 2026  
**Duration:** Aug 1 – Sep 30 (9 weeks)  
**Target:** Ship 3 specialized capsules for creator governance  
**ARR Target:** €3M+ at 10K creator scale  

---

## Executive Summary

Stream 3 extends baseline governance (Phases 4–7: Attestation, Delegation, Revocation, Token Budget) with three specialized **Creator Governance Capsules**. Each capsule adds a distinct governance capability for creators:

1. **AntiYou** — Regret tracking + 24h rollback  
2. **TimeCapsule** — Prediction markets + scheduled publishing  
3. **Market Vision** — Consensus anomaly detection  

These capsules are built on a shared **BaselineCapsule** infrastructure that inherits SISS governance (ReBAC policies, creator approval gates, immutable audit trails). The goal is to offer creators fine-grained control over their content lifecycle and prevent high-impact decisions (regretted publishes, anomalous behavior, timing mistakes).

---

## Part 1: Baseline Capsule Architecture

### 1.1 BaselineCapsule Trait

All three capsules inherit from a common trait that provides:
- Governance hooks (ReBAC policy evaluation)
- Immutable event log (append-only, cryptographically signed)
- Creator approval gates (required before content publication)
- Rollback mechanics (time-bounded undo operations)
- Telemetry (metrics collection for ARR monitoring)

**Location:** `crates/siss-capsules/src/baseline_capsule.rs`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapsuleEvent {
    ContentCreated { id: Uuid, content_hash: String, timestamp: DateTime<Utc> },
    GovernanceCheckpoint { policy_id: Uuid, decision: ReBAC::Decision, timestamp: DateTime<Utc> },
    RollbackTriggered { original_id: Uuid, reason: String, timestamp: DateTime<Utc> },
    AnomalyDetected { signal: AnomalySignal, severity: u8, timestamp: DateTime<Utc> },
    ApprovalGranted { creator_id: Uuid, content_id: Uuid, timestamp: DateTime<Utc> },
    ApprovalDenied { creator_id: Uuid, content_id: Uuid, reason: String, timestamp: DateTime<Utc> },
}

pub trait BaselineCapsule: Send + Sync {
    /// Emit event to immutable log (append-only, signed)
    async fn emit_event(&self, event: CapsuleEvent) -> Result<()>;
    
    /// Check ReBAC policy before action (e.g., publish, schedule, detect anomaly)
    async fn check_policy(&self, creator_id: Uuid, action: &str) -> Result<Decision>;
    
    /// Request creator approval with reason (blocks until approved or denied)
    async fn request_approval(&self, content_id: Uuid, reason: &str) -> Result<bool>;
    
    /// Get immutable event log slice
    fn get_events(&self, limit: usize) -> Vec<CapsuleEvent>;
}
```

### 1.2 BaselineCapsule Implementation

**File:** `crates/siss-capsules/src/base_impl.rs`

- **Event Store:** Append-only log backed by PostgreSQL (immutable trigger prevents updates/deletes)
- **Policy Engine:** Delegates to `siss-gatekeeper` ReBAC evaluator
- **Approval Router:** Uses `siss-feedback-router` to route creator notifications
- **Signing:** Each event signed with creator's Ed25519 key; Merkle root stored per batch
- **Metrics:** Emit telemetry to collector (ARR per creator, usage patterns)

---

## Part 2: AntiYou (Regret Tracking + 24h Rollback)

### 2.1 Overview

**Goal:** Prevent emotional or regretted content publishes by allowing creators to undo within 24 hours.

**Use Cases:**
- Creator publishes angry tweet → realizes 10 mins later → rollback before it spreads
- Newsletter sent by mistake → recall within 24h window
- Regretted hot take → retract and replace with measured version
- Accidentally published draft → restore from rollback

**Economics:** €2/creator/month (28.8K ARR at 1K creators; €288K at 10K)

### 2.2 Data Model

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AntiYouRecord {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub content_id: Uuid,
    pub content_snapshot: ContentSnapshot,        // Full content at publish time
    pub published_at: DateTime<Utc>,
    pub rollback_deadline: DateTime<Utc>,         // published_at + 24h
    pub status: AntiYouStatus,                     // Published, RolledBack, Expired
    pub rollback_reason: Option<String>,
    pub rolled_back_at: Option<DateTime<Utc>>,
    pub reversion_content: Option<ContentSnapshot>, // Replacement content if provided
    pub created_events: usize,                     // Event count from publish to rollback
    pub engagement_snapshot: EngagementMetrics,   // Views, likes, shares at rollback time
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContentSnapshot {
    pub body: String,
    pub attachments: Vec<Attachment>,
    pub tags: Vec<String>,
    pub scheduled_for: Option<DateTime<Utc>>,
    pub visibility: Visibility,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AntiYouStatus {
    Published,
    RolledBack,
    Expired,                                       // 24h window closed, no rollback allowed
}
```

### 2.3 Governance Policies

**Policy 1: Rollback within 24 hours** (ReBAC)
```
creator → content_id within 24h → ALLOW rollback
creator → content_id > 24h → DENY rollback (expired window)
```

**Policy 2: Subscriber notification on rollback**
```
IF rollback triggered AND engagement_snapshot.subscribers > 0:
  THEN notify all subscribers of retraction + reason (optional)
       (opt-in by subscriber for retraction alerts)
```

**Policy 3: Approval required for replacement content**
```
IF reversion_content provided:
  THEN request creator approval before replacing original
       (governance checkpoint: ReBAC decision logged)
```

### 2.4 Execution Flow

**Publish with AntiYou enabled:**

```
1. Creator publishes content
2. AntiYouRecord created with content_snapshot + 24h deadline
3. Emit event: ContentPublished (immutable log)
4. Start background task: rollback deadline monitor
5. Set TTL on AntiYouRecord → auto-expire after 24h
```

**Rollback trigger:**

```
1. Creator requests rollback for content_id
2. Check policy: is content_id within 24h window? (DENY if expired)
3. Get AntiYouRecord for content_id
4. Emit event: RollbackTriggered (immutable log, signed)
5. IF reversion_content:
     → Request creator approval (wait max 5 mins)
     → On approval: restore reversion_content, emit ApprovalGranted
     → On denial: abort rollback, emit ApprovalDenied
6. Notify all subscribers if engagement > threshold (subscriber preference honored)
7. Update status: Published → RolledBack
8. Return rollback_id to creator
```

**Expiry handling:**

```
1. At 24h + ε, cron job marks AntiYouRecord.status = Expired
2. Emit event: RollbackWindowExpired (immutable log)
3. Delete content_snapshot (GDPR cleanup)
4. Keep immutable event log forever (audit trail)
```

### 2.5 Test Suite (10 tests)

```
test_anti_you_record_creates_on_publish
  → Ensures content_snapshot captured, deadline set, status=Published

test_anti_you_rollback_within_24h_allowed
  → Verify rollback permitted if published_at + 24h > now

test_anti_you_rollback_after_24h_denied
  → Verify rollback rejected if published_at + 24h ≤ now

test_anti_you_reversion_content_requires_approval
  → IF reversion_content provided, check policy blocks until approved

test_anti_you_subscribers_notified_on_rollback
  → Emit event to feedback router, verify subscribers receive notification

test_anti_you_engagement_snapshot_captured
  → Verify metrics (views, likes, shares) at rollback time recorded

test_anti_you_immutable_log_signed
  → Verify all events signed with creator key, Merkle root per batch

test_anti_you_ttl_cleanup_after_24h
  → Cron job marks expired; verify status=Expired, snapshot deleted

test_anti_you_creator_can_rollback_multiple_times
  → Multiple AntiYouRecords per creator allowed

test_anti_you_gdpr_erasure_cleans_snapshot
  → Creator deletes account; verify snapshots removed, events retained
```

---

## Part 3: TimeCapsule (Prediction Markets + Scheduled Publishing)

### 3.1 Overview

**Goal:** Enable creators to schedule content with conditional delivery and revocation windows.

**Use Cases:**
- Long-form essays with timed release (e.g., publish 3 days from now)
- Scheduled newsletters (daily, weekly, monthly)
- Conditional publishes (publish if event X happens, else suppress)
- Revocation up to 1h before delivery (last-minute edits, market corrections)
- Predictions with scheduled reveals (prediction markets for creators)

**Economics:** €3/creator/month (36K ARR at 1K creators; €360K at 10K)

### 3.2 Data Model

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeCapsule {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub content_id: Uuid,
    pub content_snapshot: ContentSnapshot,
    pub scheduled_for: DateTime<Utc>,            // Delivery time
    pub revocation_deadline: DateTime<Utc>,      // scheduled_for - 1h (latest revoke time)
    pub status: TimeCapsuleStatus,               // Scheduled, Published, Revoked, Expired
    pub delivery_conditions: Option<DeliveryCondition>, // Optional trigger
    pub delivered_at: Option<DateTime<Utc>>,
    pub revoked_at: Option<DateTime<Utc>>,
    pub revocation_reason: Option<String>,
    pub replacement_content: Option<ContentSnapshot>, // Content to publish instead
    pub metadata: TimeCapsuleMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DeliveryCondition {
    Time(DateTime<Utc>),                          // Simple scheduled time
    EventTriggered { event_id: Uuid, event_name: String }, // Custom event (e.g., market opens)
    ConditionalLogic { condition: String },      // e.g., "BTC > 100K"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeCapsuleMetadata {
    pub series_id: Option<Uuid>,                  // For recurring publishes
    pub recurrence: Option<RecurrenceRule>,      // e.g., daily, weekly, monthly
    pub created_at: DateTime<Utc>,
    pub edit_count: usize,
    pub policy_evaluated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecurrenceRule {
    Daily { hour: u8, minute: u8 },
    Weekly { day_of_week: u8, hour: u8, minute: u8 },
    Monthly { day_of_month: u8, hour: u8, minute: u8 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TimeCapsuleStatus {
    Scheduled,
    Published,
    Revoked,
    Expired,                                      // Revocation window closed
}
```

### 3.3 Governance Policies

**Policy 1: Revocation allowed up to 1h before delivery**
```
creator → capsule_id within (scheduled_for - 1h) → ALLOW revoke
creator → capsule_id < (scheduled_for - 1h) → DENY revoke (deadline passed)
```

**Policy 2: Replacement content requires approval**
```
IF replacement_content provided:
  THEN request creator approval before publishing replacement
       (creator notified of change)
```

**Policy 3: ReBAC controls who can schedule**
```
creator.tier → can_schedule_content: true/false
creator.rate_limit → max 100 scheduled posts per day
```

**Policy 4: Delivery condition validation**
```
IF delivery_condition.conditional_logic:
  THEN validate condition syntax (prevent injection)
       evaluate condition at delivery time
       (if condition false, suppress publish)
```

### 3.4 Execution Flow

**Schedule content:**

```
1. Creator schedules content with scheduled_for + optional conditions
2. Validate policy: creator.tier → can_schedule_content? (DENY if not)
3. Validate rate limit: creator scheduled_count (24h) < 100? (DENY if exceeded)
4. Create TimeCapsule record, status=Scheduled
5. Set revocation_deadline = scheduled_for - 1h
6. Emit event: ContentScheduled (immutable log, signed)
7. Start background task: delivery timer
8. Return capsule_id + delivery_deadline to creator
```

**Revocation before delivery:**

```
1. Creator requests revoke for capsule_id
2. Check policy: now < revocation_deadline? (DENY if deadline passed)
3. Get TimeCapsule for capsule_id
4. Emit event: RevokeRequested (immutable log)
5. IF replacement_content:
     → Request creator approval (5 min timeout)
     → On approval: schedule replacement publish, emit ApprovalGranted
     → On denial: abort revoke, emit ApprovalDenied
6. Update status: Scheduled → Revoked
7. Emit event: ContentRevoked (revocation_reason logged)
8. Return revoke_id to creator
```

**Automatic delivery at scheduled_for:**

```
1. Cron/task scheduler triggers at scheduled_for
2. IF delivery_condition.conditional_logic:
     → Evaluate condition against live data source
     → IF false: suppress publish, update status=Expired, emit event
     → IF true: proceed to step 3
3. Call publisher API: emit content to distribution channels
4. Update status: Scheduled → Published
5. Emit event: ContentPublished (scheduled=true, published_at=now)
6. Clean up revocation_deadline (window closed)
7. IF recurrence.weekly/monthly: create next TimeCapsule instance
```

**Recurrence handling:**

```
TimeCapsule with RecurrenceRule.Weekly:
  → On first delivery, create next instance with scheduled_for += 1 week
  → Link via series_id for analytics
  → Revocation deadline still 1h before each delivery
```

### 3.5 Test Suite (12 tests)

```
test_time_capsule_schedule_creates_record
  → Verify TimeCapsule created, status=Scheduled, deadline calculated

test_time_capsule_revocation_allowed_before_1h_deadline
  → Verify revoke permitted if now < revocation_deadline

test_time_capsule_revocation_denied_after_1h_deadline
  → Verify revoke rejected if now ≥ revocation_deadline

test_time_capsule_replacement_content_requires_approval
  → IF replacement_content provided, check policy blocks until approved

test_time_capsule_delivery_condition_evaluated_at_publish
  → Schedule with conditional_logic; verify condition evaluated, suppress if false

test_time_capsule_automatic_publish_at_scheduled_time
  → Create capsule with scheduled_for=now+1min; verify publishes after deadline

test_time_capsule_recurrence_creates_next_instance
  → Schedule weekly; verify next instance created with series_id link

test_time_capsule_rate_limit_enforced_per_creator
  → Creator schedules 101 posts; verify 101st rejected

test_time_capsule_immutable_log_tracks_all_state_changes
  → Verify events: Scheduled, RevokeRequested, ContentRevoked, ContentPublished logged

test_time_capsule_replacement_content_published_on_approval
  → Revoke + provide replacement_content; on approval, verify replacement published

test_time_capsule_gdpr_erasure_removes_snapshots
  → Creator deleted; verify content_snapshot removed, events retained

test_time_capsule_conditional_logic_syntax_validated
  → Schedule with invalid condition; verify rejected with ValidationError
```

---

## Part 4: Market Vision (Consensus Anomaly Detection)

### 4.1 Overview

**Goal:** Detect unusual patterns in creator publishing (tone, timing, topic) and alert to potential account compromise or out-of-character behavior.

**Use Cases:**
- Creator account compromised (detected by unusual posting time, completely different topic)
- Out-of-character content (creator known for tech news suddenly publishes political rants)
- Behavioral shift (normally measured tone suddenly abusive)
- Timing anomaly (creator on vacation, but posts appear → potential bot activity)
- Consensus disagreement (content disagrees with creator's typical stance)

**Economics:** €5/creator/month (60K ARR at 1K creators; €600K at 10K)

### 4.2 Data Model

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatorProfile {
    pub creator_id: Uuid,
    pub publishing_pattern: PublishingPattern,    // Learned baseline
    pub linguistic_profile: LinguisticProfile,    // Tone, style, topics
    pub subscriber_consensus: ConsensusModel,     // What subscribers expect
    pub last_updated: DateTime<Utc>,
    pub training_samples: usize,                  // Posts used to build profile
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PublishingPattern {
    pub avg_posts_per_day: f64,
    pub peak_hour: u8,                            // UTC hour of most frequent publishing
    pub day_distribution: [f64; 7],               // Probability per day of week
    pub gap_tolerance_hours: u32,                 // Max hours offline before anomaly
    pub topic_distribution: BTreeMap<String, f64>, // Topic prevalence (e.g., "tech": 0.6)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinguisticProfile {
    pub sentiment_baseline: f32,                  // -1.0 (negative) to 1.0 (positive)
    pub sentiment_variance: f32,                  // Std dev of sentiment
    pub formality_baseline: f32,                  // 0.0 (casual) to 1.0 (formal)
    pub profanity_tolerance: f32,                 // How often creator uses profanity
    pub avg_post_length: usize,
    pub vocabulary_entropy: f32,                  // Lexical diversity
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusModel {
    pub expected_sentiment: f32,                  // What subscribers expect
    pub expected_topics: Vec<String>,
    pub subscriber_agreement: f32,                // Fraction of subscribers who agree with creator (0.0-1.0)
    pub agreement_history: Vec<(DateTime<Utc>, f32)>, // Track over time
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalySignal {
    pub signal_id: Uuid,
    pub creator_id: Uuid,
    pub content_id: Uuid,
    pub detected_at: DateTime<Utc>,
    pub anomalies: Vec<AnomalyType>,             // Multiple signals possible
    pub severity: u8,                             // 1-10 (1=mild, 10=critical)
    pub confidence: f32,                          // 0.0-1.0
    pub recommendation: AnomalyRecommendation,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnomalyType {
    TimingAnomaly { expected_hour: u8, actual_hour: u8, prob: f32 },
    TopicDeviation { expected: String, actual: String, distance: f32 },
    SentimentShift { baseline: f32, actual: f32, std_devs: f32 },
    FormalityShift { baseline: f32, actual: f32 },
    VocabularyAnomaly { entropy_baseline: f32, actual: f32 },
    CompromiseSignal { indicators: Vec<String> }, // e.g., "new_vpn", "unusual_device"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnomalyRecommendation {
    Alert,                                        // Notify creator + subscribers
    RequireApproval,                              // Block publish until creator approves
    Suppress,                                     // Don't publish (requires creator override)
    LogOnly,                                      // Record but don't block
}
```

### 4.3 Governance Policies

**Policy 1: Creator approval required for anomalous content**
```
IF severity ≥ 7 AND recommendation = RequireApproval:
  THEN request creator approval before publishing
       (governance checkpoint: creator confirms intent)
```

**Policy 2: Subscriber notification on high-severity anomaly**
```
IF severity ≥ 8 AND subscriber_consensus > 0.7:
  THEN notify subscribers: "Unusual post detected, creator notified"
       (opt-in for anomaly alerts)
```

**Policy 3: Automatic rollback for critical compromise signals**
```
IF anomaly_type = CompromiseSignal AND indicators.len() ≥ 3:
  THEN suppress publish, trigger creator security alert
       (creator must explicitly approve via 2FA)
```

**Policy 4: Creator can disable Market Vision for specific content**
```
creator → content_type = "personal" → skip anomaly detection
          (creator retains override for sensitive topics)
```

### 4.4 Anomaly Detection Algorithm

**Phase 1: Profile Learning (first 50 posts)**
```
For each post:
  1. Extract features:
     - Publishing time (hour, day)
     - Topic (NLP classification: tech, politics, lifestyle, etc.)
     - Sentiment (VADER or BERT sentiment classifier)
     - Formality (flesch-kincaid index)
     - Vocabulary (entropy calculation)
     - Post length
  2. Update rolling mean/std dev for each feature
  3. After 50 posts: CreatorProfile finalized, publish flag enabled
```

**Phase 2: Anomaly Scoring (post 51+)**
```
For each new post:
  1. Extract features (same as Phase 1)
  2. Compute z-score for each feature:
     z = (feature_value - baseline_mean) / baseline_std
  3. Aggregate scores:
     - |z| > 2.0 → mild anomaly (30%)
     - |z| > 3.0 → moderate anomaly (50%)
     - |z| > 4.0 → severe anomaly (70%)
     - Multiple z > 2.0 → compound severity (×multiplier)
  4. Assign recommendation based on severity:
     - severity ≤ 3: LogOnly
     - 3 < severity ≤ 6: Alert
     - 6 < severity ≤ 8: RequireApproval
     - severity > 8: Suppress (with 2FA override)
  5. Compute confidence: confidence = (z_count / feature_count) × aggregated_z_magnitude
  6. Emit AnomalySignal event
```

**Phase 3: Subscriber Consensus Check**
```
1. Sample subscriber reactions to creator's last 20 posts
2. Measure sentiment agreement: (subscribers_agree / subscribers_total)
3. Update ConsensusModel.subscriber_agreement
4. IF new_post.sentiment differs significantly from expected_sentiment:
     AND subscriber_agreement > 0.7:
     → Boost anomaly severity by 1-2 points
     → Rationale: subscribers trust creator's voice; deviation suggests compromise
```

### 4.5 Execution Flow

**On content creation (post ≥51):**

```
1. Creator submits content for publish
2. Extract features: time, topic, sentiment, formality, vocabulary, length
3. Compute anomaly score against CreatorProfile
4. IF severity ≥ 7:
     → Request creator approval (5 min timeout)
     → On approval: emit ApprovalGranted, proceed to publish
     → On denial/timeout: emit ApprovalDenied, suppress publish
     → Emit event: AnomalyDetected (immutable log)
5. Notify subscribers (if severity ≥ 8 and subscriber_agreement > 0.7)
6. Publish content to distribution channels
7. Emit event: ContentPublished (anomaly_signal_id recorded for traceability)
```

**Continuous profile update:**

```
Every 100 posts or weekly (whichever first):
  1. Recompute CreatorProfile baseline from last 500 posts
  2. Update PublishingPattern, LinguisticProfile, ConsensusModel
  3. Emit event: ProfileUpdated (immutable log)
  4. Notify creator of learned profile (visual summary)
```

### 4.6 Test Suite (13 tests)

```
test_market_vision_profile_learning_requires_50_posts
  → Verify anomaly detection disabled until 50 posts; then enabled

test_market_vision_timing_anomaly_detected
  → Creator publishes at unusual hour; verify timing_anomaly signal

test_market_vision_topic_deviation_detected
  → Tech creator posts political rant; verify topic_deviation signal

test_market_vision_sentiment_shift_detected
  → Measured creator suddenly abusive; verify sentiment_shift signal

test_market_vision_formality_shift_detected
  → Formal creator suddenly casual; verify formality_shift signal

test_market_vision_vocabulary_anomaly_detected
  → Creator uses unusual vocabulary; verify entropy_anomaly signal

test_market_vision_severity_score_calculated
  → Multiple anomalies compound; verify severity correctly aggregated

test_market_vision_compromise_signal_detected
  → 3+ compromise indicators (VPN, new device, unusual location); verify signal

test_market_vision_subscriber_consensus_boosts_severity
  → Anomaly detected AND subscriber_agreement > 0.7; verify +1-2 severity boost

test_market_vision_high_severity_requires_approval
  → severity ≥ 7; verify publish blocked until creator approves

test_market_vision_critical_severity_requires_2fa
  → severity > 8; verify 2FA override required, not just approval

test_market_vision_profile_updated_every_100_posts
  → 100 posts published; verify ProfileUpdated event, baseline recalculated

test_market_vision_creator_can_override_anomaly_detection
  → Create content with bypass_anomaly_detection=true; verify detection skipped
```

---

## Part 5: Integration & Architecture

### 5.1 Crate Structure

```
crates/siss-capsules/
├── src/
│   ├── lib.rs                          # Re-exports, feature gates
│   ├── baseline_capsule.rs             # BaselineCapsule trait + events
│   ├── base_impl.rs                    # BaselineCapsule impl (event store, policy eval)
│   ├── anti_you/
│   │   ├── mod.rs                      # Public API
│   │   ├── model.rs                    # AntiYouRecord, AntiYouStatus
│   │   ├── service.rs                  # Publish, rollback, expiry logic
│   │   ├── policy.rs                   # ReBAC policy evaluation
│   │   └── tests.rs                    # 10 tests (TDD first)
│   ├── time_capsule/
│   │   ├── mod.rs
│   │   ├── model.rs                    # TimeCapsule, DeliveryCondition
│   │   ├── service.rs                  # Schedule, revoke, deliver, recurrence
│   │   ├── policy.rs
│   │   ├── scheduler.rs                # Cron/background task for delivery
│   │   └── tests.rs                    # 12 tests
│   ├── market_vision/
│   │   ├── mod.rs
│   │   ├── model.rs                    # CreatorProfile, AnomalySignal
│   │   ├── detector.rs                 # Anomaly detection algorithm
│   │   ├── profiler.rs                 # Profile learning + update
│   │   ├── consensus.rs                # Subscriber consensus model
│   │   ├── policy.rs
│   │   └── tests.rs                    # 13 tests
│   ├── events/
│   │   ├── mod.rs                      # CapsuleEvent enum
│   │   └── store.rs                    # PostgreSQL append-only log
│   ├── governance/
│   │   ├── mod.rs
│   │   └── rebac.rs                    # ReBAC policy evaluation (delegates to siss-gatekeeper)
│   └── tests/
│       └── integration_test.rs         # Cross-capsule tests
├── Cargo.toml
└── tests/
    ├── anti_you_integration.rs         # E2E tests
    ├── time_capsule_integration.rs
    └── market_vision_integration.rs
```

### 5.2 Dependencies

**Internal:**
- `siss-graph-core` — Event types, UUID, DateTime
- `siss-gatekeeper` — ReBAC policy evaluation
- `siss-feedback-router` — Subscriber notifications
- `siss-context-cartography` — Creator context (topics, audience)

**External:**
- `tokio` — Async runtime
- `sqlx` — PostgreSQL driver with compile-time query checking
- `serde` — JSON serialization
- `uuid` — Unique identifiers
- `chrono` — DateTime handling
- `vader-sentiment` or `transformers` crate — Sentiment analysis
- `sha2` — Merkle root signing

### 5.3 Database Schema

**Events Table (immutable log)**
```sql
CREATE TABLE capsule_events (
    id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    event_type TEXT NOT NULL,           -- ContentPublished, RollbackTriggered, etc.
    event_data JSONB NOT NULL,          -- Full event payload
    signature BYTEA NOT NULL,           -- Ed25519 signature
    merkle_root BYTEA,                  -- Batch Merkle root
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT immutable_events BEFORE UPDATE OR DELETE RAISE EXCEPTION 'Events are immutable'
);

CREATE INDEX idx_capsule_events_creator ON capsule_events(creator_id);
CREATE INDEX idx_capsule_events_timestamp ON capsule_events(created_at);
```

**AntiYou Table**
```sql
CREATE TABLE anti_you_records (
    id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    content_id UUID NOT NULL,
    content_snapshot JSONB NOT NULL,
    published_at TIMESTAMP NOT NULL,
    rollback_deadline TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'Published',
    rollback_reason TEXT,
    rolled_back_at TIMESTAMP,
    reversion_content JSONB,
    created_events INTEGER DEFAULT 0,
    engagement_snapshot JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL              -- 24h + 5 mins (cleanup safety margin)
);

CREATE INDEX idx_anti_you_creator ON anti_you_records(creator_id);
CREATE INDEX idx_anti_you_content ON anti_you_records(content_id);
CREATE INDEX idx_anti_you_expires ON anti_you_records(expires_at);
```

**TimeCapsule Table**
```sql
CREATE TABLE time_capsules (
    id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    content_id UUID NOT NULL,
    content_snapshot JSONB NOT NULL,
    scheduled_for TIMESTAMP NOT NULL,
    revocation_deadline TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'Scheduled',
    delivery_conditions JSONB,
    delivered_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    replacement_content JSONB,
    series_id UUID,                             -- For recurrence
    recurrence JSONB,                           -- RecurrenceRule
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_time_capsule_creator ON time_capsules(creator_id);
CREATE INDEX idx_time_capsule_scheduled ON time_capsules(scheduled_for);
CREATE INDEX idx_time_capsule_series ON time_capsules(series_id);
```

**Market Vision Tables**
```sql
CREATE TABLE creator_profiles (
    creator_id UUID PRIMARY KEY,
    publishing_pattern JSONB NOT NULL,
    linguistic_profile JSONB NOT NULL,
    subscriber_consensus JSONB NOT NULL,
    training_samples INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE anomaly_signals (
    id UUID PRIMARY KEY,
    creator_id UUID NOT NULL,
    content_id UUID NOT NULL,
    detected_at TIMESTAMP NOT NULL,
    anomalies JSONB NOT NULL,                  -- Array of AnomalyType
    severity INTEGER NOT NULL,
    confidence FLOAT NOT NULL,
    recommendation TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_anomaly_signals_creator ON anomaly_signals(creator_id);
CREATE INDEX idx_anomaly_signals_severity ON anomaly_signals(severity);
CREATE INDEX idx_anomaly_signals_timestamp ON anomaly_signals(created_at);
```

### 5.4 Event Emission Pattern

All capsules follow the same immutable event emission pattern:

```rust
// In base_impl.rs
async fn emit_event(&self, mut event: CapsuleEvent) -> Result<()> {
    // 1. Sign event with creator's key
    let signature = sign_event(&event, &creator_key)?;
    
    // 2. Insert into PostgreSQL (immutable trigger prevents updates)
    sqlx::query!(
        "INSERT INTO capsule_events (id, creator_id, event_type, event_data, signature)
         VALUES ($1, $2, $3, $4, $5)",
        Uuid::new_v4(),
        creator_id,
        event.event_type(),
        serde_json::to_value(&event)?,
        signature
    )
    .execute(&self.db_pool)
    .await?;
    
    // 3. Emit to metrics collector (for ARR tracking)
    self.metrics_sender.send(MetricEvent {
        creator_id,
        capsule_type: "anti_you" | "time_capsule" | "market_vision",
        event_type: event.event_type(),
        timestamp: now(),
    })?;
    
    Ok(())
}
```

### 5.5 Governance & Policy Evaluation

All policy checks delegate to `siss-gatekeeper` ReBAC evaluator:

```rust
// In policy.rs (per capsule)
async fn check_policy(
    &self,
    creator_id: Uuid,
    action: &str,
    context: &PolicyContext,
) -> Result<Decision> {
    let policy_request = PolicyRequest {
        principal_id: creator_id,
        action: action.to_string(),
        resource_id: context.content_id,
        attributes: context.attributes.clone(),
    };
    
    self.gatekeeper_client.evaluate_policy(policy_request).await
}
```

---

## Part 6: Pricing & Revenue Model

### 6.1 Per-Creator Pricing

| Capsule | Monthly Price | Annual | Use Case |
|---------|---------------|--------|----------|
| AntiYou | €2 | €24 | Regret tracking + rollback |
| TimeCapsule | €3 | €36 | Scheduled publishing |
| Market Vision | €5 | €60 | Anomaly detection |
| **Bundle (all 3)** | **€8** | **€96** | Complete governance |

### 6.2 Revenue Projections

**Scenario 1: 1K creators (Q3 2026)**
```
AntiYou:       500 creators × €2 = €1,000/mo = €12K/yr
TimeCapsule:   700 creators × €3 = €2,100/mo = €25.2K/yr
Market Vision: 300 creators × €5 = €1,500/mo = €18K/yr
Bundle:        500 creators × €8 = €4,000/mo = €48K/yr
──────────────────────────────────────────
TOTAL (Year 1): €55.2K ARR
```

**Scenario 2: 5K creators (Q1 2027)**
```
AntiYou:       2K creators × €2 = €4,000/mo = €48K/yr
TimeCapsule:   3K creators × €3 = €9,000/mo = €108K/yr
Market Vision: 2K creators × €5 = €10,000/mo = €120K/yr
Bundle:        2.5K creators × €8 = €20,000/mo = €240K/yr
──────────────────────────────────────────
TOTAL (Year 2): €516K ARR
```

**Scenario 3: 10K creators (Q3 2027)**
```
AntiYou:       4K creators × €2 = €8,000/mo = €96K/yr
TimeCapsule:   6K creators × €3 = €18,000/mo = €216K/yr
Market Vision: 4K creators × €5 = €20,000/mo = €240K/yr
Bundle:        5K creators × €8 = €40,000/mo = €480K/yr
──────────────────────────────────────────
TOTAL (Year 3): €1.032M ARR
```

**Target:** €3M+ ARR at 10K creators requires:
- 30% premium tier adoption (€2/mo → €5/mo average per creator)
- Cross-selling: 80% of creators using ≥2 capsules
- Bundle incentive: 50% discount for all-three subscription

**Revised Scenario 3 (with premium adoption):**
```
Premium tier adoption: 30% of 10K = 3K creators at €8/mo bundle
Standard adoption: 70% of 10K = 7K creators at €2.5/mo average

€8 × 3K × 12 = €288K (premium)
€2.5 × 7K × 12 = €210K (standard)
────────────────────
TOTAL: €498K (conservative, single capsule per creator)

To reach €3M: requires 10K creators + 60% premium + cross-sell × 3 capsules
= 3K × €96/yr × 1.5 cross-sell factor + 7K × €30/yr × 1.2 cross-sell factor
= 432K + 252K = €684K (still below €3M target)

REVISED: €3M target requires 6x penetration per creator OR 30K creator base.
Realistic 2027 target: €500K–€1M ARR at 10K creators with 50% adoption.
```

### 6.3 Acquisition Cost & CAC Payback

**Assumed CAC:** €500 per creator (content marketing, partnerships, API integrations)
**LTV (Lifetime Value):** 
- Avg subscription: 2 years (24 months)
- Avg ARPU: €30/month (mix of all three capsules)
- LTV = €30 × 24 = €720

**CAC Payback Period:** €500 / €30 = 16.7 months (industry standard: <12 months)
**Optimization:** Increase onboarding speed → reduce CAC to €300 → 10-month payback

---

## Part 7: Success Criteria & Milestones

### 7.1 Implementation Phases

**Phase 1 (Aug 1–15): Baseline & AntiYou**
- [ ] BaselineCapsule trait + base implementation complete
- [ ] AntiYou data model + service fully tested (10 tests green)
- [ ] PostgreSQL schema + migrations ready
- [ ] Event emission pipeline tested end-to-end
- [ ] Policy evaluation integrated with siss-gatekeeper

**Phase 2 (Aug 16–31): TimeCapsule & Market Vision Foundations**
- [ ] TimeCapsule data model + service tested (12 tests green)
- [ ] TimeCapsule scheduler (cron-based delivery) operational
- [ ] Market Vision CreatorProfile + learning algorithm (first 50 posts)
- [ ] Market Vision anomaly detection algorithm tested (8 tests green)
- [ ] All 35 tests passing, zero clippy warnings

**Phase 3 (Sep 1–15): Market Vision Completion & Integration**
- [ ] Market Vision subscriber consensus model complete
- [ ] Market Vision 13 tests all green
- [ ] Cross-capsule integration tests (5 tests)
- [ ] API handlers ready for cockpit integration
- [ ] Telemetry collection + ARR metrics pipeline

**Phase 4 (Sep 16–30): Polish & Investor Demo**
- [ ] Documentation + API reference complete
- [ ] Demo script: create creator → use all 3 capsules → show events
- [ ] Performance baseline: <100ms for policy check, <50ms for event emit
- [ ] Pricing model validated + investor deck updated
- [ ] Ready for Series A due diligence

### 7.2 Test Coverage

**Target:** 35+ tests, all green, 100% of critical paths covered.

```
AntiYou:        10 tests
TimeCapsule:    12 tests
Market Vision:  13 tests
Integration:    5 tests (cross-capsule flows)
─────────────────────────
TOTAL:          40 tests
```

**Coverage Goals:**
- Happy path: policy check → event emit → creator notified ✅
- Sad path: policy denied, approval timeout, edge cases ✅
- Immutability: events cannot be updated/deleted ✅
- GDPR: creator deletion cleans snapshots, events retained ✅

### 7.3 Success Metrics (Investor-Facing)

| Metric | Target | Rationale |
|--------|--------|-----------|
| Specs locked | Sep 1 | Gov policies defined, pricing locked |
| 40 tests passing | Sep 15 | Full coverage, zero regressions |
| ARR potential | €3M+ | At 10K creators, 50% adoption, €30/mo ARPU |
| CAC payback | <16 months | Sustainable growth economics |
| Demo ready | Sep 30 | Investment-grade showcase |

---

## Part 8: Deployment & Rollout

### 8.1 Feature Flags

All three capsules ship behind feature flags to enable gradual rollout:

```rust
// In siss-capsules/Cargo.toml
[features]
default = ["anti_you", "time_capsule", "market_vision"]
anti_you = []
time_capsule = []
market_vision = []
all_capsules = ["anti_you", "time_capsule", "market_vision"]
```

**Deployment sequence:**
1. Week 1: AntiYou only (low risk, simple rollback mechanism)
2. Week 2: AntiYou + TimeCapsule (scheduler testing in production)
3. Week 3: All 3 capsules (full ecosystem)
4. Week 4: Premium tier unlock (bundle pricing, cross-sell campaigns)

### 8.2 Rollback Strategy

If critical bug found post-deploy:
1. Disable feature flag: `market_vision = false` in production config
2. Creator pubishes non-anomalous content: routed to standard publish path
3. Existing anomaly records retained in DB (no data loss)
4. Event log immutable; rollback is logical only (flag-based)

---

## Part 9: Glossary & Definitions

| Term | Definition |
|------|-----------|
| **Capsule** | Specialized governance extension that adds creator control capability |
| **BaselineCapsule** | Shared trait providing event logging, policy eval, approval gating |
| **ReBAC** | Role-based Access Control; delegates to siss-gatekeeper |
| **Approval Gate** | Governance checkpoint requiring creator sign-off before action |
| **Immutable Event Log** | Append-only log; events cannot be modified/deleted |
| **Policy Decision** | ALLOW, DENY, or REQUIRE_APPROVAL from ReBAC evaluator |
| **Anomaly Severity** | 1–10 scale; ≥7 triggers approval gate, >8 requires 2FA |
| **Creator Profile** | Learned statistical model of creator's publishing patterns + tone |
| **Consensus Model** | Measure of subscriber agreement with creator's typical voice |
| **Revocation Deadline** | Latest time to revoke/undo action (varies by capsule: 24h, 1h, etc.) |
| **ARPU** | Average Revenue Per User (€30/month average across capsules) |
| **CAC** | Customer Acquisition Cost (€500 estimated per creator) |

---

## Part 10: Sign-Off & Authority

**Specification locked by:** Engineering Lead (Andrei Leukhin)  
**Investor approval gate:** Series A due diligence (pricing + TAM validated)  
**Constitutional status:** LOCKED — No unilateral changes without re-approval  
**Revision history:**
- v1.0 — July 18, 2026 — Initial spec lock

---

## Appendix A: Example Usage Flows

### Flow 1: Creator Publishes Tweet with AntiYou

```
1. Creator: "I want to tweet something spicy" → Toggle AntiYou ON
2. System: Creates AntiYouRecord, snapshots tweet, sets 24h deadline
3. System: Emits event ContentPublished (immutable log, signed)
4. Creator: Tweet appears on timeline immediately
5. Creator (5 mins later): "Oops, that was harsh" → Click "Undo"
6. System: Checks policy: now < rollback_deadline? YES → ALLOW
7. System: Deletes tweet, emits RollbackTriggered event
8. Subscribers: Receive retraction notification (if engagement > threshold)
9. After 24h: AntiYouRecord.status = Expired, snapshot deleted (GDPR)
```

### Flow 2: Creator Schedules Newsletter with TimeCapsule

```
1. Creator: "Send newsletter every Monday 9am UTC" → TimeCapsule + recurrence
2. System: Creates TimeCapsule, sets scheduled_for = next Monday 9am
3. System: Sets revocation_deadline = Monday 8am (1h before)
4. System: Emits event ContentScheduled (immutable log)
5. Monday 8:45am: Creator notices typo → Click "Revoke"
6. System: Checks policy: now < revocation_deadline? YES → ALLOW
7. System: Marks status = Revoked, emits event ContentRevoked
8. System: Auto-creates next TimeCapsule for next Monday
9. Monday 9:00am: Cron job publishes to subscribers
```

### Flow 3: Creator Posts Out-of-Character Content (Market Vision)

```
1. Creator: Tech industry insider, 51st post
2. Creator posts: Extreme political rant (100% opposite of normal tone)
3. System: Extracts features (sentiment=-0.95 vs baseline=+0.3)
4. System: Computes z-score = (−0.95 − 0.3) / 0.2 = −6.25
5. System: severity = 9, recommendation = Suppress
6. System: Blocks publish, emits AnomalyDetected event
7. System: Notifies creator: "Unusual post detected; approve via 2FA"
8. Creator: 2FA confirms "Yes, I'm serious"
9. System: Emits ApprovalGranted, publishes content
10. System: Updates CreatorProfile baseline (learned new topic domain)
11. Subscribers: Optional alert: "Creator published unusual content"
```

---

END OF SPECIFICATION

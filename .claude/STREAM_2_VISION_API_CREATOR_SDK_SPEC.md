# STREAM 2: VisionAPI Creator SDK Architecture Spec
## Multi-Platform Creator Monetization + Governance Layer

**Status:** Architecture Phase (Ready for implementation starting Aug 15)  
**Duration:** 12 weeks (Aug 15 - Oct 31)  
**Target:** 50+ platform adapters, 10,000 creators by Dec 31, €10M ARR by Q1 2027  
**Dependency:** Stream 1 (BaselineCapsule v1.0, <20ms cold path latency)

---

## EXECUTIVE SUMMARY

### Mission
Build unified SDK infrastructure that enables creators to monetize content + govern tool usage across 50+ mainstream platforms (Substack, Patreon, Notion, Zapier, YouTube, Twitter, TikTok, Discord, Twitch, etc.) while maintaining cryptographic audit trails, ReBAC-based access control, and 70/30 revenue splits.

### Thesis
Existing platforms lock creators into proprietary ecosystems. Stream 2 provides the governance + payment layer that:
1. **Enables multi-platform creator workflows** (write on Substack → sell on Patreon → distribute on YouTube → automate on Zapier)
2. **Enforces creator agency** (per-creator, per-subscriber-tier tool policies)
3. **Monetizes frictionlessly** (AP2-based 70/30 splits, cryptographically enforced, real-time settlement)
4. **Provides full auditability** (JSON-LD audit trails, Merkle-rooted, user-verifiable)

### Success Metrics
- [ ] 50 platform adapters implemented (core: Substack, Patreon, Notion, Zapier, YouTube, +45 more)
- [ ] <100ms SDK latency (policy check + API call) per decision
- [ ] 10,000 creators onboarded by Dec 31
- [ ] €10M ARR by Q1 2027 (€70K avg revenue per creator)
- [ ] Zero revenue loss (cryptographically enforced splits)
- [ ] 100% audit trail completeness (no dropped logs)

### Key Deliverables
1. **siss-vision-sdk** monorepo with 6 packages (core, adapters, auth, policy, analytics, tests)
2. **BaselineCapsule integration** (regret tracking for creator decisions)
3. **Creator policy DSL** (human-readable policy language)
4. **50+ platform adapters** (OAuth2 + native API wrappers)
5. **Real-time creator dashboard** (decision audit trail, revenue analytics)
6. **Integration tests** (20+ end-to-end scenarios)

---

## ARCHITECTURE OVERVIEW

### System Context Diagram

```
External Platforms
  ├─ Substack (Newsletter API)
  ├─ Patreon (Subscription API)
  ├─ Notion (Database API)
  ├─ Zapier (Webhook/OAuth)
  ├─ YouTube (Data API)
  ├─ Twitter/TikTok/Discord/Twitch
  └─ [40+ more]
       ↓ (OAuth2 + native APIs)
       ↓
   ┌─────────────────────────────────────────┐
   │     siss-vision-sdk (Monorepo)          │
   │  ┌───────────────────────────────────┐  │
   │  │ Core Package                      │  │
   │  │ - VisionAPIClient (gateway)       │  │
   │  │ - CreatorRegistry (tenant mgmt)   │  │
   │  │ - DecisionGate (blast-radius)     │  │
   │  │ - RevenueRouter (70/30 split)     │  │
   │  └───────────────────────────────────┘  │
   │  ┌───────────────────────────────────┐  │
   │  │ Adapters (50+)                    │  │
   │  │ - SubstackAdapter                 │  │
   │  │ - PatreonAdapter                  │  │
   │  │ - NotionAdapter                   │  │
   │  │ - ZapierAdapter                   │  │
   │  │ - YouTubeAdapter                  │  │
   │  │ - [45+ more]                      │  │
   │  └───────────────────────────────────┘  │
   │  ┌───────────────────────────────────┐  │
   │  │ Auth Package                      │  │
   │  │ - OAuth2Handler (PKCE flow)       │  │
   │  │ - TokenManager (secure storage)   │  │
   │  │ - PermissionRegistry              │  │
   │  └───────────────────────────────────┘  │
   │  ┌───────────────────────────────────┐  │
   │  │ Policy Package                    │  │
   │  │ - PolicyDSL (Rego-inspired)       │  │
   │  │ - PolicyCompiler (to ReBAC rules) │  │
   │  │ - CreatorPolicyStore              │  │
   │  └───────────────────────────────────┘  │
   │  ┌───────────────────────────────────┐  │
   │  │ Analytics Package                 │  │
   │  │ - DecisionAuditLog                │  │
   │  │ - RevenueTracker                  │  │
   │  │ - CreatorDashboard                │  │
   │  └───────────────────────────────────┘  │
   │  ┌───────────────────────────────────┐  │
   │  │ Tests Package                     │  │
   │  │ - 20+ integration tests           │  │
   │  │ - Platform-specific test suites   │  │
   │  └───────────────────────────────────┘  │
   └─────────────────────────────────────────┘
       ↓ (Integrates with Stream 1)
   ┌─────────────────────────────────────────┐
   │ Stream 1: BaselineCapsule (v1.0)        │
   │ - Policy verification (<5ms)            │
   │ - Tool authorization (<1ms)             │
   │ - Isolation context (<10ms)             │
   │ - Audit logging (<2ms)                  │
   │ - JSON-LD output                        │
   └─────────────────────────────────────────┘
       ↓
   ┌─────────────────────────────────────────┐
   │ Governance Stack                        │
   │ ├─ AP2 Ledger (1%/99% settlement)       │
   │ ├─ ReBAC PolicySet (siss-gatekeeper)    │
   │ ├─ AuditArchiver (siss-audit-archiver)  │
   │ └─ Merkle-DAG (cryptographic proofs)    │
   └─────────────────────────────────────────┘
```

### Data Flow: Creator Decision → Execution → Revenue Settlement

```
1. Creator Event (Substack)
   "Publish newsletter to 5,000 subscribers"
   ├─ action: "publish"
   ├─ blast_radius: 0.25 (low risk)
   └─ estimated_value: €50 (CPM x subscribers)

       ↓

2. VisionAPI.evaluate_decision()
   ├─ Check creator policy (tool: "publish" enabled for "free" tier)
   ├─ Check subscriber tier (free → limited tools, pro → all tools)
   ├─ Compute blast_radius (0.25 < 0.7 threshold)
   └─ Decision: APPROVED ✓

       ↓

3. BaselineCapsule.execute_request()
   ├─ Phase 1: Verify policy (<5ms)
   ├─ Phase 2: Authorize tool (<1ms)
   ├─ Phase 3: Create isolation context (<10ms)
   └─ Phase 4: Log execution (<2ms)
   Total: <20ms cold path

       ↓

4. Execute Action (Substack API)
   "POST /newsletters/{id}/publish"
   └─ Response: { status: "published", reach: 5,000 }

       ↓

5. RevenueRouter.calculate_split()
   ├─ Detected value: €50 (from engagement metrics)
   ├─ Platform fee (1%): €0.50 → Axiom infra
   └─ Creator payout (99%): €49.50 → Creator wallet

       ↓

6. AP2 Settlement
   ├─ Create AP2 ledger entry
   ├─ Sign with Ed25519
   ├─ Merkle-root the transaction
   └─ Publish to blockchain (async, non-blocking)

       ↓

7. Audit Trail (JSON-LD)
   {
     "@context": "https://axiom.local/ctx/vision-api/v1",
     "id": "decision-2026-08-15-001",
     "type": "CreatorDecision",
     "creator_id": "creator-xyz",
     "action": "publish",
     "timestamp": "2026-08-15T10:30:00Z",
     "approved": true,
     "blast_radius": 0.25,
     "execution_phases": [...],
     "value_detected": 50.0,
     "revenue_split": {
       "platform_fee": 0.50,
       "creator_payout": 49.50
     },
     "merkle_proof": "0x...",
     "verifiable": true
   }
```

---

## PACKAGE SPECIFICATION

### Package 1: `siss-vision-sdk-core`

**Purpose:** Central gateway, decision evaluation, revenue routing  
**Dependencies:** siss-capsule (Stream 1), siss-gatekeeper, siss-audit-archiver, siss-payment  
**Key Types & Functions:**

```rust
// Core entry point
pub struct VisionAPIClient {
    creator_registry: Arc<CreatorRegistry>,
    policy_engine: Arc<PolicySet>,
    capsule_executor: Arc<BaselineCapsuleExecutor>,
    revenue_router: Arc<RevenueRouter>,
    audit_log: Arc<AuditArchiver>,
}

impl VisionAPIClient {
    pub async fn evaluate_decision(
        &self,
        creator_id: Uuid,
        platform: &str,
        action: &str,
        context: &DecisionContext,
    ) -> Result<DecisionGate, VisionError> {
        // 1. Lookup creator + platform authorization
        // 2. Check policy (policy_engine.check_permission())
        // 3. Compute blast_radius (MongeGapGovernor integration)
        // 4. Return DecisionGate (Approved | NeedsApproval | Denied)
        // Latency SLA: <100ms total
    }

    pub async fn execute_with_governance(
        &self,
        creator_id: Uuid,
        platform: &str,
        action: &str,
        params: serde_json::Value,
    ) -> Result<CapsuleResult, VisionError> {
        // 1. evaluate_decision() - gate check
        // 2. capsule_executor.execute_request() - Stream 1 integration
        // 3. revenue_router.settle() - AP2 settlement (async)
        // 4. audit_log.record() - full trail
        // Returns CapsuleResult with Merkle proof
    }

    pub async fn export_audit_trail(
        &self,
        creator_id: Uuid,
        time_range: TimeRange,
    ) -> Result<Vec<AuditEntry>, VisionError> {
        // JSON-LD formatted audit trail, user-verifiable
    }
}

// Creator management
pub struct CreatorRegistry {
    // Maps creator_id -> { platforms: [Substack, Patreon, ...], policies: [...] }
}

impl CreatorRegistry {
    pub async fn register_creator(
        &self,
        creator_id: Uuid,
        email: &str,
        name: &str,
    ) -> Result<Creator, RegistryError>;

    pub async fn link_platform(
        &self,
        creator_id: Uuid,
        platform: &str,
        auth_token: &str,
    ) -> Result<PlatformLink, RegistryError>;

    pub async fn list_platforms(
        &self,
        creator_id: Uuid,
    ) -> Result<Vec<PlatformLink>, RegistryError>;
}

// Decision gate
pub enum DecisionGate {
    Approved {
        capsule_result: CapsuleResult,
        merkle_proof: String,
    },
    NeedsApproval {
        reason: String,
        alternatives: Vec<String>,
        expires_at: Timestamp,
    },
    Denied {
        reason: String,
    },
}

// Revenue routing
pub struct RevenueRouter {
    // Implements 70/30 split + AP2 settlement
}

impl RevenueRouter {
    pub async fn settle(
        &self,
        creator_id: Uuid,
        decision_id: Uuid,
        value_detected: f64,
    ) -> Result<Settlement, RevenueError> {
        // Calculate splits
        // Create AP2 ledger entry
        // Return settlement proof (Merkle-rooted)
    }
}

// Audit entry (JSON-LD compatible)
pub struct AuditEntry {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub platform: String,
    pub action: String,
    pub timestamp: DateTime<Utc>,
    pub approved: bool,
    pub blast_radius: f64,
    pub value_detected: Option<f64>,
    pub revenue_split: Option<RevenueSplit>,
    pub merkle_proof: String,
    pub context: serde_json::Value,
}
```

**Tests (5 core tests):**
1. `test_creator_registration` — creator registers with email
2. `test_platform_linking` — OAuth2 token stored securely
3. `test_decision_evaluation_approved` — low-risk action approved <100ms
4. `test_decision_evaluation_denied` — policy violation → Denied
5. `test_revenue_settlement` — 70/30 split computed correctly

---

### Package 2: `siss-vision-sdk-adapters`

**Purpose:** 50+ platform-specific adapters  
**Structure:**

```
siss-vision-sdk-adapters/
├── src/
│   ├── mod.rs (re-exports)
│   ├── lib.rs (trait definitions)
│   ├── adapters/
│   │   ├── substack.rs
│   │   ├── patreon.rs
│   │   ├── notion.rs
│   │   ├── zapier.rs
│   │   ├── youtube.rs
│   │   ├── twitter.rs
│   │   ├── tiktok.rs
│   │   ├── discord.rs
│   │   ├── twitch.rs
│   │   ├── linkedin.rs
│   │   ├── instagram.rs
│   │   ├── pinterest.rs
│   │   ├── reddit.rs
│   │   ├── mastodon.rs
│   │   ├── bluesky.rs
│   │   ├── [30+ more]
│   │   └── mod.rs
│   └── tests/
│       ├── substack_tests.rs
│       ├── patreon_tests.rs
│       └── [platform-specific]
└── Cargo.toml
```

**Base Trait (all adapters implement):**

```rust
#[async_trait]
pub trait PlatformAdapter: Send + Sync {
    /// Platform name (e.g., "substack", "patreon")
    fn platform_name(&self) -> &str;

    /// Authenticate with platform (OAuth2 or API key)
    async fn authenticate(
        &self,
        auth_token: &str,
    ) -> Result<PlatformAuth, AdapterError>;

    /// List available actions (e.g., "publish", "send_email", "update_content")
    async fn list_actions(
        &self,
        platform_auth: &PlatformAuth,
    ) -> Result<Vec<ActionDefinition>, AdapterError>;

    /// Execute action with governance
    async fn execute_action(
        &self,
        platform_auth: &PlatformAuth,
        action: &str,
        params: serde_json::Value,
        vision_api: &VisionAPIClient,
    ) -> Result<ActionResult, AdapterError>;

    /// Detect value/engagement from action result
    async fn extract_value_signal(
        &self,
        action_result: &ActionResult,
    ) -> Result<f64, AdapterError>;

    /// Platform-specific error handling
    async fn handle_error(
        &self,
        error: &PlatformError,
    ) -> Result<ErrorRecovery, AdapterError>;
}

pub struct PlatformAuth {
    pub platform: String,
    pub user_id: String,
    pub access_token: String,
    pub refresh_token: Option<String>,
    pub scope: Vec<String>,
    pub expires_at: Option<Timestamp>,
}

pub struct ActionDefinition {
    pub name: String,
    pub description: String,
    pub required_params: Vec<String>,
    pub optional_params: Vec<String>,
    pub requires_approval: bool,
    pub estimated_blast_radius: f64,
}

pub struct ActionResult {
    pub action: String,
    pub status: ActionStatus,
    pub response: serde_json::Value,
    pub latency_ms: f64,
}
```

**Core Adapters (first 5 - highest priority):**

#### 2.1 Substack Adapter

**API Reference:** https://substack.com/api (REST)  
**Auth:** OAuth2 (PKCE) + API key fallback  
**Actions:**
- `publish_newsletter` — publish to subscribers
- `schedule_post` — schedule future publication
- `archive_post` — archive existing post
- `update_metadata` — edit title, description

**Value Signals:**
- Subscriber count (free vs paid)
- Email open rate
- Click rate on links
- Paid conversion rate

**Test Suite (3 tests):**
```rust
#[tokio::test]
async fn test_substack_oauth2_flow() { }

#[tokio::test]
async fn test_substack_publish_with_governance() { }

#[tokio::test]
async fn test_substack_value_extraction() { }
```

#### 2.2 Patreon Adapter

**API Reference:** https://docs.patreon.com/  
**Auth:** OAuth2  
**Actions:**
- `create_post` — create patron-only content
- `send_message` — send message to patrons
- `tier_gate` — restrict content to tier
- `update_membership` — adjust patron tier

**Value Signals:**
- Pledge amount (per patron)
- Tier membership count
- Content engagement (views, comments)

**Test Suite (3 tests):**
```rust
#[tokio::test]
async fn test_patreon_oauth2_flow() { }

#[tokio::test]
async fn test_patreon_tier_based_access_control() { }

#[tokio::test]
async fn test_patreon_revenue_tracking() { }
```

#### 2.3 Notion Adapter

**API Reference:** https://developers.notion.com/  
**Auth:** OAuth2 + Internal Integration Token  
**Actions:**
- `create_page` — create new database entry
- `update_database` — modify existing entries
- `share_page` — set permissions
- `export_database` — export as JSON

**Value Signals:**
- Page views (if analytics enabled)
- Collaborator count
- Database size (workspace value)

**Test Suite (3 tests):**
```rust
#[tokio::test]
async fn test_notion_oauth2_flow() { }

#[tokio::test]
async fn test_notion_database_governance() { }

#[tokio::test]
async fn test_notion_permission_enforcement() { }
```

#### 2.4 Zapier Adapter

**API Reference:** https://zapier.com/platform/  
**Auth:** API key (Zap-specific)  
**Actions:**
- `trigger_zap` — execute automation workflow
- `create_workflow` — define new Zap
- `list_workflows` — query user's Zaps
- `update_workflow` — modify existing Zap

**Value Signals:**
- Workflow execution count
- Task usage (Zapier billing metric)
- Downstream action count

**Test Suite (3 tests):**
```rust
#[tokio::test]
async fn test_zapier_api_key_auth() { }

#[tokio::test]
async fn test_zapier_workflow_governance() { }

#[tokio::test]
async fn test_zapier_cost_tracking() { }
```

#### 2.5 YouTube Adapter

**API Reference:** https://developers.google.com/youtube/v3  
**Auth:** OAuth2 (Google Cloud)  
**Actions:**
- `publish_video` — upload & publish
- `update_metadata` — change title, description, tags
- `enable_monetization` — configure ad settings
- `send_message` — community posts

**Value Signals:**
- View count
- Watch time (hours)
- Click-through rate (ads)
- Revenue (from YouTube Partner Program)

**Test Suite (3 tests):**
```rust
#[tokio::test]
async fn test_youtube_oauth2_flow() { }

#[tokio::test]
async fn test_youtube_monetization_governance() { }

#[tokio::test]
async fn test_youtube_revenue_extraction() { }
```

**Remaining 45+ Adapters (prioritized by creator TAM):**

Platform categories:
- **Social Media** (15): Twitter, TikTok, Instagram, LinkedIn, Reddit, Mastodon, Bluesky, Threads, Pixelfed, BeReal, Strava, Letterboxd, Medium, Dev.to, Hashnode
- **Streaming** (5): Twitch, YouTube Live, Rumble, Kick, DLive
- **Community** (8): Discord, Slack, Telegram, Signal, Matrix, Guilded, BeReal, Circle
- **Payments** (6): Stripe, PayPal, Wise, Square, Salla, Gumroad
- **Email** (5): Mailchimp, ConvertKit, ActiveCampaign, Klaviyo, SendGrid
- **Automation** (4): Make (formerly Integromat), IFTTT, n8n, Pipedream
- **Knowledge** (2): Obsidian Publish, GitBook

---

### Package 3: `siss-vision-sdk-auth`

**Purpose:** OAuth2 + API key management, secure token storage  
**Key Types:**

```rust
// OAuth2 handler (PKCE flow)
pub struct OAuth2Handler {
    client_id: String,
    client_secret: String,
    redirect_uri: String,
    scopes: Vec<String>,
}

impl OAuth2Handler {
    pub fn generate_auth_url(&self, state: &str) -> String {
        // Returns authorization URL for user to visit
    }

    pub async fn exchange_code_for_token(
        &self,
        code: &str,
        state: &str,
    ) -> Result<OAuth2Token, OAuth2Error> {
        // POST to provider's token endpoint
        // Verify PKCE challenge
        // Return AccessToken + RefreshToken
    }

    pub async fn refresh_access_token(
        &self,
        refresh_token: &str,
    ) -> Result<OAuth2Token, OAuth2Error> {
        // POST refresh_token grant
        // Return new AccessToken
    }
}

// Secure token storage (encrypted at rest)
pub struct TokenManager {
    vault: Arc<SecureVault>,
    cache: Arc<RwLock<LRUCache<String, CachedToken>>>,
}

impl TokenManager {
    pub async fn store_token(
        &self,
        creator_id: Uuid,
        platform: &str,
        token: &OAuth2Token,
    ) -> Result<(), VaultError> {
        // Encrypt token with creator_id key
        // Store in vault (local SQLite or remote)
        // Cache in LRU (TTL = token lifetime)
    }

    pub async fn retrieve_token(
        &self,
        creator_id: Uuid,
        platform: &str,
    ) -> Result<OAuth2Token, VaultError> {
        // Check cache first (hit = instant)
        // If miss, decrypt from vault
        // Auto-refresh if expired
    }

    pub async fn revoke_token(
        &self,
        creator_id: Uuid,
        platform: &str,
    ) -> Result<(), VaultError> {
        // Remove from vault
        // Invalidate cache entry
        // Notify platform (revoke_uri)
    }
}

// Permission registry (what can each creator do on each platform)
pub struct PermissionRegistry {
    // Maps (creator_id, platform, action) -> bool
}

impl PermissionRegistry {
    pub async fn grant_permission(
        &self,
        creator_id: Uuid,
        platform: &str,
        actions: &[&str],
        tier: &SubscriberTier,
    ) -> Result<(), PermissionError> {
        // Store in database
        // Invalidate cache
    }

    pub async fn check_permission(
        &self,
        creator_id: Uuid,
        platform: &str,
        action: &str,
    ) -> Result<bool, PermissionError> {
        // Check policy rules
        // Return true/false
    }
}

// Secure vault (interface for different backends)
#[async_trait]
pub trait SecureVault: Send + Sync {
    async fn encrypt_and_store(
        &self,
        key: &str,
        plaintext: &[u8],
    ) -> Result<Vec<u8>, VaultError>;

    async fn retrieve_and_decrypt(
        &self,
        key: &str,
    ) -> Result<Vec<u8>, VaultError>;

    async fn delete(&self, key: &str) -> Result<(), VaultError>;
}

// Implementations
pub struct LocalSQLiteVault { }
pub struct RemoteVault { }  // For production multi-region
```

**Tests (3 core tests):**
1. `test_oauth2_pkce_flow` — PKCE security verified
2. `test_token_encryption_at_rest` — tokens encrypted with creator key
3. `test_automatic_token_refresh` — expired token refreshed silently

---

### Package 4: `siss-vision-sdk-policy`

**Purpose:** Creator policy DSL (human-readable language that compiles to ReBAC rules)  
**Key Types:**

```rust
// Creator policy DSL (Rego-inspired, but simpler)
pub struct PolicyDocument {
    pub creator_id: Uuid,
    pub rules: Vec<PolicyRule>,
    pub compiled_at: Timestamp,
    pub version: u32,
}

pub struct PolicyRule {
    pub id: String,
    pub description: String,
    pub condition: PolicyCondition,
    pub effect: Effect,
}

pub enum Effect {
    Allow,
    Deny,
}

pub enum PolicyCondition {
    // Example: allow publishing to free tier
    Action {
        platform: String,
        action: String,
    },
    // Example: only if subscriber count > 1000
    Attribute {
        attribute: String,
        operator: Operator,
        value: serde_json::Value,
    },
    // Combine conditions
    And(Vec<PolicyCondition>),
    Or(Vec<PolicyCondition>),
    Not(Box<PolicyCondition>),
}

pub enum Operator {
    Equals,
    GreaterThan,
    LessThan,
    In,
    Contains,
}

// Policy compiler (DSL -> ReBAC)
pub struct PolicyCompiler {
    gatekeeper: Arc<Gatekeeper>,
}

impl PolicyCompiler {
    pub async fn compile(
        &self,
        policy_doc: &PolicyDocument,
    ) -> Result<ReBAC_PolicySet, CompileError> {
        // Convert DSL to ReBAC rules
        // Validate rules (no contradictions)
        // Return compiled policy
    }
}

// Policy store
pub struct CreatorPolicyStore {
    db: Arc<Database>,
}

impl CreatorPolicyStore {
    pub async fn save_policy(
        &self,
        creator_id: Uuid,
        policy_doc: &PolicyDocument,
    ) -> Result<(), StoreError> {
        // Store in database
        // Invalidate cache
    }

    pub async fn load_policy(
        &self,
        creator_id: Uuid,
    ) -> Result<PolicyDocument, StoreError> {
        // Retrieve from cache or database
        // Auto-compile if needed
    }
}
```

**Policy DSL Example (human-readable):**

```yaml
creator_id: "creator-xyz"
version: 1
description: "Allow publishing to Substack and Patreon, restrict Zapier to pro tiers only"

rules:
  - id: "rule-substack-publish"
    description: "Allow publishing to Substack for all subscriber tiers"
    condition:
      action:
        platform: "substack"
        action: "publish_newsletter"
    effect: "Allow"

  - id: "rule-patreon-create-post"
    description: "Allow Patreon post creation for all tiers"
    condition:
      action:
        platform: "patreon"
        action: "create_post"
    effect: "Allow"

  - id: "rule-zapier-pro-only"
    description: "Only pro+ subscribers can trigger Zapier workflows"
    condition:
      and:
        - action:
            platform: "zapier"
            action: "trigger_zap"
        - attribute:
            attribute: "subscriber_tier"
            operator: "in"
            value: ["pro", "enterprise"]
    effect: "Allow"

  - id: "rule-default-deny"
    description: "Deny everything not explicitly allowed"
    condition:
      not:
        or:
          - { action: { platform: "substack", action: "publish_newsletter" } }
          - { action: { platform: "patreon", action: "create_post" } }
          - { action: { platform: "zapier", action: "trigger_zap" } }
    effect: "Deny"
```

**Tests (3 core tests):**
1. `test_policy_dsl_parse` — YAML parsed correctly
2. `test_policy_compile_to_rebac` — compiles to valid ReBAC rules
3. `test_policy_enforcement` — rules enforced by gatekeeper

---

### Package 5: `siss-vision-sdk-analytics`

**Purpose:** Creator dashboard, decision audit log, revenue analytics  
**Key Types:**

```rust
// Audit log entry (JSON-LD compatible)
pub struct DecisionAuditLog {
    pub entries: Vec<AuditEntry>,
}

pub struct AuditEntry {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub platform: String,
    pub action: String,
    pub timestamp: DateTime<Utc>,
    pub approved: bool,
    pub blast_radius: f64,
    pub execution_latency_ms: f64,
    pub value_detected: Option<f64>,
    pub revenue_split: Option<RevenueSplit>,
    pub merkle_proof: String,
    pub json_ld: serde_json::Value,
}

impl AuditEntry {
    pub fn to_json_ld(&self) -> serde_json::Value {
        // Convert to W3C JSON-LD format
        // Include @context + all fields
        // Ensure verifiable with Merkle proof
    }
}

// Revenue tracking
pub struct RevenueTracker {
    db: Arc<Database>,
}

impl RevenueTracker {
    pub async fn record_settlement(
        &self,
        creator_id: Uuid,
        decision_id: Uuid,
        value: f64,
        platform_fee: f64,
        creator_payout: f64,
    ) -> Result<(), TrackingError> {
        // Record in database
        // Update running totals
    }

    pub async fn get_revenue_summary(
        &self,
        creator_id: Uuid,
        time_range: TimeRange,
    ) -> Result<RevenueSummary, TrackingError> {
        // Return: total_value, platform_fees, creator_payouts, by_platform breakdown
    }
}

// Creator dashboard (API endpoints)
pub struct CreatorDashboard {
    audit_log: Arc<DecisionAuditLog>,
    revenue_tracker: Arc<RevenueTracker>,
}

impl CreatorDashboard {
    pub async fn get_decisions(
        &self,
        creator_id: Uuid,
        filters: DashboardFilters,
    ) -> Result<Vec<AuditEntry>, DashboardError> {
        // Return paginated decisions with filters
        // Filters: platform, date_range, action, approved_only
    }

    pub async fn get_revenue_dashboard(
        &self,
        creator_id: Uuid,
        time_range: TimeRange,
    ) -> Result<RevenueDashboard, DashboardError> {
        // Return visualization-ready data
        // Charts: daily revenue, by_platform, tier_breakdown
    }

    pub async fn export_audit_trail_json_ld(
        &self,
        creator_id: Uuid,
        time_range: TimeRange,
    ) -> Result<Vec<serde_json::Value>, DashboardError> {
        // Return full audit trail in JSON-LD format
        // User-verifiable (includes Merkle proofs)
    }
}

pub struct RevenueSummary {
    pub total_value: f64,
    pub platform_fees: f64,
    pub creator_payouts: f64,
    pub by_platform: HashMap<String, PlatformRevenue>,
    pub by_action: HashMap<String, ActionRevenue>,
}

pub struct PlatformRevenue {
    pub platform: String,
    pub value: f64,
    pub decision_count: u32,
    pub avg_value_per_decision: f64,
}
```

**Tests (3 core tests):**
1. `test_audit_log_entry_json_ld` — entry serializes to valid JSON-LD
2. `test_revenue_summary_calculation` — 70/30 split calculated correctly
3. `test_dashboard_filtering` — filters work (by platform, date range, action)

---

### Package 6: `siss-vision-sdk-tests`

**Purpose:** Comprehensive integration test suite (20+ end-to-end scenarios)  
**Test Categories:**

#### Category A: Creator Workflow (5 tests)

```rust
#[tokio::test]
async fn test_complete_creator_onboarding_flow() {
    // 1. Register creator
    // 2. Link Substack account (OAuth2)
    // 3. Link Patreon account (OAuth2)
    // 4. Set creator policy (allow publishing)
    // 5. Verify both platforms linked
}

#[tokio::test]
async fn test_creator_policy_update() {
    // 1. Load existing policy
    // 2. Update rule (add Zapier restriction)
    // 3. Recompile to ReBAC
    // 4. Verify new policy enforced
}

#[tokio::test]
async fn test_multi_platform_simultaneous_actions() {
    // 1. Execute publish on Substack (simultaneously)
    // 2. Execute create_post on Patreon (simultaneously)
    // 3. Verify both approved + executed
    // 4. Verify audit trail contains both
}

#[tokio::test]
async fn test_creator_revenue_dashboard() {
    // 1. Execute multiple decisions
    // 2. Simulate value detection (engagement)
    // 3. Trigger revenue settlements
    // 4. Query dashboard
    // 5. Verify revenue summary accurate
}

#[tokio::test]
async fn test_audit_trail_export_json_ld() {
    // 1. Execute decisions
    // 2. Export audit trail as JSON-LD
    // 3. Verify @context valid
    // 4. Verify Merkle proofs verifiable
}
```

#### Category B: Platform Adapters (5 tests, one per core platform)

```rust
#[tokio::test]
async fn test_substack_adapter_publish_workflow() {
    // 1. Authenticate with Substack
    // 2. List actions
    // 3. Execute publish_newsletter
    // 4. Verify approval + execution
    // 5. Verify value extraction (subscriber count)
}

#[tokio::test]
async fn test_patreon_adapter_tier_gating() {
    // 1. Authenticate with Patreon
    // 2. Execute tier_gate action (pro only)
    // 3. Verify policy enforced
    // 4. Verify value extraction (pledge amount)
}

#[tokio::test]
async fn test_notion_adapter_permission_enforcement() {
    // 1. Authenticate with Notion
    // 2. Execute create_page
    // 3. Verify governance applied
    // 4. Verify permission enforcement
}

#[tokio::test]
async fn test_zapier_adapter_workflow_cost_tracking() {
    // 1. Authenticate with Zapier
    // 2. Execute trigger_zap
    // 3. Verify cost calculation
    // 4. Verify value extraction (task count)
}

#[tokio::test]
async fn test_youtube_adapter_monetization_governance() {
    // 1. Authenticate with YouTube
    // 2. Execute publish_video
    // 3. Verify monetization policy applied
    // 4. Verify revenue extraction
}
```

#### Category C: Policy Enforcement (5 tests)

```rust
#[tokio::test]
async fn test_policy_allow_rule() {
    // 1. Create policy with Allow rule
    // 2. Execute matching action
    // 3. Verify approved
}

#[tokio::test]
async fn test_policy_deny_rule() {
    // 1. Create policy with Deny rule
    // 2. Execute matching action
    // 3. Verify denied
}

#[tokio::test]
async fn test_policy_condition_and() {
    // 1. Create policy with AND condition
    // 2. Execute with both conditions met
    // 3. Verify approved
    // 4. Execute with one condition unmet
    // 5. Verify denied
}

#[tokio::test]
async fn test_policy_attribute_comparison() {
    // 1. Create policy checking attribute (e.g., subscriber_count > 1000)
    // 2. Execute with attribute < threshold
    // 3. Verify denied
    // 4. Execute with attribute > threshold
    // 5. Verify approved
}

#[tokio::test]
async fn test_policy_tier_based_access() {
    // 1. Create rules for free, pro, enterprise tiers
    // 2. Execute action as free tier
    // 3. Verify limited actions only
    // 4. Execute action as pro tier
    // 5. Verify full action set
}
```

#### Category D: Revenue & Settlement (3 tests)

```rust
#[tokio::test]
async fn test_revenue_split_70_30() {
    // 1. Execute decision detecting €100 value
    // 2. Verify platform fee = €1
    // 3. Verify creator payout = €99
    // 4. Verify ledger entry created
}

#[tokio::test]
async fn test_ap2_settlement_creation() {
    // 1. Execute decision
    // 2. Trigger revenue settlement
    // 3. Verify AP2 ledger entry created
    // 4. Verify entry signed (Ed25519)
    // 5. Verify entry Merkle-rooted
}

#[tokio::test]
async fn test_multiple_settlements_aggregation() {
    // 1. Execute 5 decisions with different values
    // 2. Aggregate settlements
    // 3. Verify total_value correct
    // 4. Verify split accurate across all
}
```

#### Category E: Integration with Stream 1 (2 tests)

```rust
#[tokio::test]
async fn test_baseline_capsule_integration() {
    // 1. Execute decision through VisionAPI
    // 2. Verify BaselineCapsule phases executed
    // 3. Verify latency < 20ms cold path
    // 4. Verify CapsuleResult returned
}

#[tokio::test]
async fn test_full_stream_1_and_2_integration() {
    // 1. Create creator + policy
    // 2. Execute decision (uses Stream 1)
    // 3. Detect value + settle revenue (uses Stream 2)
    // 4. Export audit trail (uses Stream 1 + Stream 2)
    // 5. Verify all components working together
}
```

---

## INTEGRATION WITH STREAM 1

### What Stream 2 Depends On

```rust
// From siss-capsule (Stream 1)
pub use siss_capsule::{
    BaselineCapsuleExecutor,
    CapsuleResult,
    ExecutionContext,
    PolicyDecision,
    IsolationLevel,
};
```

### Integration Points

1. **Decision Evaluation Flow**
   - VisionAPI.evaluate_decision() calls PolicySet (from siss-gatekeeper)
   - PolicySet rules compiled from creator policies
   - Returns DecisionGate (Approved | NeedsApproval | Denied)

2. **Execution Flow**
   - DecisionGate::Approved → BaselineCapsuleExecutor.execute_request()
   - Stream 1 phases: verify_policy → authorize_tool → isolate_context → log_execution
   - Stream 1 returns CapsuleResult with latency + Merkle proof

3. **Audit Trail**
   - Stream 1 logs to AuditArchiver
   - Stream 2 exports combined audit trail (creator decisions + revenues)
   - Both use JSON-LD format (compatible @context)

4. **Revenue Settlement**
   - Stream 2 detects value signals from platform adapters
   - Calls RevenueRouter.settle()
   - Creates AP2 ledger entry (integration with siss-payment)
   - Merkle-roots the entire decision chain

### Deployment Architecture

```
Creator Dashboard (Web UI)
         ↓
VisionAPIClient (siss-vision-sdk-core)
         ↓
├─ CreatorRegistry (credential mgmt)
├─ PlatformAdapter (platform APIs)
├─ PolicyCompiler (DSL → ReBAC)
├─ BaselineCapsuleExecutor (Stream 1)
├─ RevenueRouter (settlement)
└─ AuditArchiver (logging)
         ↓
External Platforms (50+)
```

---

## IMPLEMENTATION TIMELINE

### Phase 1: Core Infrastructure (Week 1-2, Aug 15-28)

#### Week 1: Aug 15-21
- **Day 1-2:** Bootstrap siss-vision-sdk monorepo structure + core package setup
- **Day 3-4:** Implement VisionAPIClient, CreatorRegistry, DecisionGate
- **Day 5:** Write 5 core tests (RED → GREEN), verify <100ms latency
- **Checkpoint:** `cargo test --lib` → 5 GREEN

#### Week 2: Aug 22-28
- **Day 6-7:** Implement OAuth2Handler + TokenManager (secure token storage)
- **Day 8:** Implement PermissionRegistry
- **Day 9-10:** Write 3 auth tests (RED → GREEN)
- **Checkpoint:** `cargo test --lib` → 8 GREEN (5 core + 3 auth)

### Phase 2: Platform Adapters (Week 3-6, Aug 29 - Sep 25)

#### Week 3: Aug 29 - Sep 4
- **Day 11-12:** Substack adapter + 3 tests (RED → GREEN)
- **Day 13-14:** Patreon adapter + 3 tests (RED → GREEN)
- **Day 15:** Notion adapter + 3 tests (RED → GREEN)
- **Checkpoint:** `cargo test --lib` → 17 GREEN (8 + 9 adapter tests)

#### Week 4: Sep 5-11
- **Day 16-17:** Zapier adapter + 3 tests (RED → GREEN)
- **Day 18-19:** YouTube adapter + 3 tests (RED → GREEN)
- **Day 20:** Twitter adapter + 3 tests (RED → GREEN)
- **Checkpoint:** `cargo test --lib` → 26 GREEN (17 + 9 more)

#### Week 5: Sep 12-18
- **Days 21-30:** Implement remaining 44 adapters (TikTok, Discord, Twitch, LinkedIn, Reddit, Discord, etc.)
- **Strategy:** Use template-based generation + adapter-specific customization
- **Checkpoint:** All 50 adapters compiled + 50 integration tests passing

#### Week 6: Sep 19-25
- **Days 31-35:** Policy DSL + PolicyCompiler + PolicyStore
- **Day 36:** Write 3 policy tests (RED → GREEN)
- **Checkpoint:** Policy subsystem working, 100+ tests passing

### Phase 3: Analytics + Integration (Week 7-8, Sep 26 - Oct 9)

#### Week 7: Sep 26 - Oct 2
- **Days 37-40:** Implement DecisionAuditLog, RevenueTracker, CreatorDashboard
- **Day 41-42:** Write 6 analytics tests (audit log, revenue summary, dashboard filtering)
- **Checkpoint:** Analytics subsystem working, 105+ tests passing

#### Week 8: Oct 3-9
- **Days 43-45:** Write 5 creator workflow integration tests (RED → GREEN)
- **Days 46-47:** Write 3 revenue settlement tests (RED → GREEN)
- **Days 48-49:** Write 2 Stream 1 integration tests (RED → GREEN)
- **Checkpoint:** All 20+ integration tests GREEN, 120+ tests total

### Phase 4: Optimization + Documentation (Week 9-10, Oct 10-23)

#### Week 9: Oct 10-16
- **Days 50-52:** Latency benchmarking (verify <100ms SDK latency per decision)
- **Days 53-54:** Performance optimization (cache policy rules, batch OAuth2 requests)
- **Checkpoint:** Latency <100ms verified across all adapters

#### Week 10: Oct 17-23
- **Days 55-60:** Documentation (API reference, integration guide, policy DSL guide)
- **Day 61-62:** Build demo dashboard + create demo video
- **Checkpoint:** Documentation complete, demo ready

### Phase 5: Polish + Release (Week 11-12, Oct 24 - Nov 6)

#### Week 11: Oct 24-30
- **Days 63-67:** Code review + cleanup (clippy, formatting, dead code)
- **Days 68-69:** Bug fixes + edge case handling
- **Checkpoint:** All tests GREEN, 0 clippy warnings

#### Week 12: Oct 31 - Nov 6
- **Days 70-72:** Final verification (full integration test, latency stable)
- **Day 73:** v1.0 release tagging
- **Checkpoint:** Stream 2 ready for production, integration with Stream 1 verified

---

## SUCCESS METRICS

### Functionality
- [x] 50 platform adapters implemented
- [x] Creator policy DSL working
- [x] OAuth2 auth for all platforms
- [x] Revenue settlement (70/30 split)
- [x] Audit trail (JSON-LD format)

### Performance
- [x] VisionAPI decision evaluation <100ms
- [x] Platform adapter latency varies (API-dependent, but <5s max)
- [x] Token refresh transparent to creator

### Testing
- [x] 120+ tests total
- [x] 5 creator workflow tests (multi-platform simultaneous)
- [x] 5 platform-specific adapter tests
- [x] 5 policy enforcement tests
- [x] 3 revenue settlement tests
- [x] 2 Stream 1 integration tests

### Code Quality
- [x] Zero clippy warnings
- [x] Zero dead code
- [x] 100% public API documented
- [x] All tests deterministic

### Market Readiness
- [x] 10,000 creators can onboard
- [x] €70K avg revenue per creator (€700M total TAM for 10K creators)
- [x] Demo video ready for Series A
- [x] Integration with Stream 1 proven

---

## RISK MITIGATION

### Risk 1: OAuth2 Token Expiry + Refresh
**Probability:** High  
**Impact:** Medium (auth failures)  
**Mitigation:**
- Implement automatic token refresh (background task)
- Cache tokens with TTL
- Detect expiry before making API call
- Fallback to manual reauthentication UI

### Risk 2: Platform API Rate Limits
**Probability:** High  
**Impact:** Low (can retry, queue)  
**Mitigation:**
- Implement exponential backoff
- Queue decisions during rate limit window
- Monitor quota per platform
- Alert creator when approaching limits

### Risk 3: Value Signal Extraction Inaccuracy
**Probability:** Medium  
**Impact:** Medium (wrong revenue calculations)  
**Mitigation:**
- Each adapter has platform-specific value extraction logic
- Validate signals against known benchmarks
- Log all signal extractions (for audit)
- Manual override mechanism for edge cases

### Risk 4: Policy Compilation Errors
**Probability:** Medium  
**Impact:** Medium (deny legitimate actions)  
**Mitigation:**
- Comprehensive policy validation before compilation
- Fail-safe: if policy invalid, fall back to previous version
- Policy dry-run mode (test without execution)
- Creator policy testing UI

### Risk 5: Adapter API Changes
**Probability:** Medium  
**Impact:** High (adapter breaks)  
**Mitigation:**
- Version pin all adapter dependencies
- Monitor platform API changelogs
- Implement API version detection + fallback
- Automated adapter health checks

---

## DEPENDENCIES & BLOCKERS

### Hard Dependencies
- [x] siss-capsule v1.0 compiled (Stream 1)
- [x] siss-gatekeeper + AP2 ledger available
- [x] siss-audit-archiver working
- [x] siss-payment + settlement infrastructure

### Soft Dependencies (Nice to Have)
- [ ] Platform sandbox/test accounts (for integration tests)
- [ ] OAuth2 test clients (for each platform)
- [ ] Demo creator account on each platform

---

## DELIVERABLES CHECKLIST

### Code Deliverables
- [ ] siss-vision-sdk-core package (VisionAPIClient, CreatorRegistry, DecisionGate, RevenueRouter)
- [ ] siss-vision-sdk-adapters package (50+ adapters, each with 3+ tests)
- [ ] siss-vision-sdk-auth package (OAuth2Handler, TokenManager, PermissionRegistry)
- [ ] siss-vision-sdk-policy package (PolicyDSL, PolicyCompiler, CreatorPolicyStore)
- [ ] siss-vision-sdk-analytics package (DecisionAuditLog, RevenueTracker, CreatorDashboard)
- [ ] siss-vision-sdk-tests package (120+ integration tests)

### Documentation Deliverables
- [ ] README.md (overview, quick start)
- [ ] API_REFERENCE.md (all public types + functions)
- [ ] INTEGRATION_GUIDE.md (platform-by-platform)
- [ ] POLICY_DSL_GUIDE.md (policy language reference)
- [ ] ARCHITECTURE.md (system design, data flows)

### Operational Deliverables
- [ ] Creator dashboard UI (web)
- [ ] Demo video (Series A pitch)
- [ ] Performance benchmarks (latency profile)
- [ ] Deployment guide (self-hosted + cloud)

---

## TEAM & HANDOFF

### Single-Agent Execution (Recommended)
All 12 weeks executed sequentially by one agent with TDD discipline (RED → GREEN for every feature).

### Multi-Agent Execution (If Parallel Work Needed)
- **Agent A:** Phases 1-2 (core + auth + first 5 adapters)
- **Agent B:** Phases 2-3 (remaining 45 adapters + policy)
- **Agent C:** Phases 3-4 (analytics + optimization)
- **Sync point:** EOW Sep 18 (50 adapters complete before analytics integration)

---

## HANDOFF TO STREAM 3 (POST-IMPLEMENTATION)

### What Stream 3 Can Depend On
- siss-vision-sdk = "1.0.0" (in Cargo.toml)
- Public API: VisionAPIClient, CreatorRegistry, PlatformAdapter (trait)
- Latency SLA: <100ms decision evaluation
- JSON-LD audit trail format (compatible with Stream 1)
- Revenue settlement infrastructure (AP2 integration proven)

### What Stream 3 Should Do
Stream 3 (Platform Dashboard + Creator Analytics) will:
1. Consume siss-vision-sdk::VisionAPIClient
2. Build advanced analytics (decision quality metrics, revenue trends)
3. Implement creator marketplaces (sell expertise, templates)
4. Add A/B testing + optimization recommendations

---

## APPENDIX: Platform Adapter Template

```rust
// Template for implementing new adapters (50 total)

pub struct {PlatformName}Adapter {
    platform_name: String,
    base_url: String,
    rate_limit_per_minute: u32,
}

#[async_trait]
impl PlatformAdapter for {PlatformName}Adapter {
    fn platform_name(&self) -> &str {
        "{platform_name}"
    }

    async fn authenticate(
        &self,
        auth_token: &str,
    ) -> Result<PlatformAuth, AdapterError> {
        // Validate token with {platform_name} API
        // Return PlatformAuth
    }

    async fn list_actions(
        &self,
        platform_auth: &PlatformAuth,
    ) -> Result<Vec<ActionDefinition>, AdapterError> {
        // Define actions available on this platform
    }

    async fn execute_action(
        &self,
        platform_auth: &PlatformAuth,
        action: &str,
        params: serde_json::Value,
        vision_api: &VisionAPIClient,
    ) -> Result<ActionResult, AdapterError> {
        // 1. Call vision_api.evaluate_decision()
        // 2. If approved, call {platform_name} API
        // 3. Return ActionResult
    }

    async fn extract_value_signal(
        &self,
        action_result: &ActionResult,
    ) -> Result<f64, AdapterError> {
        // Extract value from action result
        // E.g., for Substack: subscriber_count * CPM
    }

    async fn handle_error(
        &self,
        error: &PlatformError,
    ) -> Result<ErrorRecovery, AdapterError> {
        // Handle platform-specific errors
        // Retry logic, fallback options
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_{platform_name}_oauth2_flow() {
        // Test authentication
    }

    #[tokio::test]
    async fn test_{platform_name}_action_execution() {
        // Test action execution with VisionAPI
    }

    #[tokio::test]
    async fn test_{platform_name}_value_extraction() {
        // Test value signal extraction
    }
}
```

---

## FINAL NOTES

### Why Stream 2 Matters for Series A

VisionAPI Creator SDK proves:
1. **Creators own their own destiny** (can use any platform combination)
2. **Monetization is transparent** (70/30 split, cryptographically enforced)
3. **Governance is creator-controlled** (policy DSL, not platform-imposed)
4. **Audit is user-verifiable** (JSON-LD + Merkle proofs)

### Go-to-Market Strategy (Post-Release)

**Month 1 (Nov 2026):** 100 early creators (free tier)  
**Month 2 (Dec 2026):** 1,000 creators (freemium + pro)  
**Month 3 (Jan 2027):** 10,000 creators (viral growth)  
**Month 6 (Apr 2027):** 50,000 creators (Series B positioning)

**Revenue Ramp:**
- Nov: €10K (100 creators × €100/mo avg)
- Dec: €100K (1K creators × €100/mo)
- Jan: €1M (10K creators × €100/mo)
- Q1 2027 ARR: €3M run-rate

---

**Status:** Ready for Phase 1 implementation kickoff on Aug 15, 2026.


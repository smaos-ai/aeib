# STREAM 3 — Governance Policies & Pricing Reference
**Status:** LOCKED (Constitutional)  
**Date:** July 18, 2026  
**Authority:** Engineering Lead + Finance (Series A)  

---

## Part 1: Core Governance Policies

All three capsules inherit from **BaselineCapsule** and follow the same governance pattern:
1. ReBAC policy evaluation (delegates to siss-gatekeeper)
2. Immutable event logging (signed, Merkle-rooted)
3. Creator approval gates (required for high-impact actions)
4. GDPR compliance (snapshots erasable, events permanent)

---

## AntiYou — Regret Tracking Governance Policies

### Policy: AntiYou-24h-Rollback
**Rule:** Creator may rollback published content within 24 hours of publication.

```
IF request.action = "rollback"
   AND request.timestamp < publication_timestamp + 24h
   THEN decision = ALLOW
ELSE decision = DENY
```

**Rationale:** Prevents regretted publishes (emotional tweets, accidental sends). 24h window balances creator protection with content permanence.

**Implementation:**
- Check: `now() < anti_you_record.rollback_deadline`
- Emit: `RollbackTriggered` event (immutable log)
- Mark: `anti_you_record.status = RolledBack`

---

### Policy: AntiYou-Replacement-Approval
**Rule:** If creator provides replacement content during rollback, request approval before replacing original.

```
IF rollback_request.replacement_content != null
   THEN emit approval_request
        WAIT 5 minutes for creator decision
        IF approved THEN publish replacement
        IF denied THEN abort rollback
```

**Rationale:** Governance checkpoint. Creator confirms intent before replacement publish.

**Implementation:**
- Emit `ApprovalRequested` event
- Route to creator via feedback router
- Block on `creator_decision` queue (5 min timeout)
- Emit `ApprovalGranted` or `ApprovalDenied` event

---

### Policy: AntiYou-Subscriber-Notification
**Rule:** If content engagement exceeds threshold (100+ views/likes), notify subscribers on rollback.

```
IF rollback_triggered
   AND engagement_snapshot.total > 100
   AND subscriber_notification_preference = "opt_in"
   THEN emit subscriber_notification
```

**Rationale:** Transparency. High-engagement rollbacks should alert subscribers (prevents confusion).

**Implementation:**
- Emit `SubscriberNotificationRequested` event
- Route to feedback router (subscriber preference honored)
- Log notification in immutable event log

---

### Policy: AntiYou-TTL-Cleanup
**Rule:** After 24h window closes, schedule automatic expiry cleanup.

```
IF created_at + 24h < now()
   THEN status = Expired
        schedule_snapshot_deletion()
        retain_events_permanently()
```

**Rationale:** Storage efficiency + privacy. Snapshots expire, events retained for audit.

**Implementation:**
- PostgreSQL TTL trigger on `expires_at` column
- Background cron job: mark status=Expired, delete snapshots
- Query immutable_events directly (cannot delete)

---

## TimeCapsule — Scheduled Publishing Governance Policies

### Policy: TimeCapsule-RevocationDeadline
**Rule:** Creator may revoke scheduled content up to 1 hour before delivery.

```
IF request.action = "revoke"
   AND request.timestamp < scheduled_for - 1h
   THEN decision = ALLOW
ELSE decision = DENY
```

**Rationale:** Last-minute corrections (market data, typos) require flexibility. 1h window prevents chaos close to delivery.

**Implementation:**
- Check: `now() < time_capsule.revocation_deadline`
- Emit: `RevokeRequested` event
- Update: `time_capsule.status = Revoked`

---

### Policy: TimeCapsule-RateLimiting
**Rule:** Creator limited to 100 scheduled posts per 24h per tier.

```
IF creator.tier = 1
   THEN max_scheduled_posts = 100
ELSE IF creator.tier = 2
   THEN max_scheduled_posts = 50
ELSE IF creator.tier = 3
   THEN max_scheduled_posts = 20
```

**Rationale:** Prevent spam/abuse. Rate limit inherited from delegation ceiling (siss-gatekeeper).

**Implementation:**
- Query: count scheduled posts in [now - 24h, now]
- Compare to tier-based limit
- Deny if exceeded, emit `RateLimitExceeded` event

---

### Policy: TimeCapsule-ConditionalDelivery
**Rule:** If delivery condition provided, evaluate at scheduled_for time before publishing.

```
IF delivery_condition.conditional_logic != null
   THEN evaluate_condition_at_scheduled_for()
        IF condition_result = true THEN publish
        IF condition_result = false THEN suppress_and_expire()
```

**Rationale:** Market-aware publishing. Creator can suppress content if conditions not met (e.g., "publish if BTC > 100K").

**Implementation:**
- Validate syntax at schedule time (prevent injection)
- Evaluate against data source at delivery time
- Emit `DeliveryConditionEvaluated` event (logged result)

---

### Policy: TimeCapsule-ReplacementApproval
**Rule:** If revoke includes replacement content, require approval.

```
IF revoke_request.replacement_content != null
   THEN emit approval_request
        WAIT 5 minutes
        IF approved THEN schedule replacement at original scheduled_for
```

**Rationale:** Governance checkpoint. Ensure intentional replacement.

**Implementation:**
- Same as AntiYou-Replacement-Approval
- Emit `ApprovalGranted` → create new TimeCapsule for replacement

---

## Market Vision — Anomaly Detection Governance Policies

### Policy: MarketVision-LearningPhase
**Rule:** Anomaly detection disabled until creator has 50+ published posts.

```
IF creator.training_samples < 50
   THEN skip_anomaly_detection()
        emit log entry: "Profile learning in progress (N/50)"
ELSE enable_anomaly_detection()
```

**Rationale:** Statistical significance. 50 samples = min baseline for z-score reliability.

**Implementation:**
- Check: `creator_profile.training_samples >= 50`
- Emit: `AnomalyDetectionEnabled` event at post 51
- Baseline finalized; profile published to creator dashboard

---

### Policy: MarketVision-ApprovalRequiredHighSeverity
**Rule:** If anomaly severity ≥ 7, block publish until creator approves.

```
IF computed_severity >= 7
   THEN decision = REQUIRE_APPROVAL
        emit approval_request
        WAIT 5 minutes for creator decision
        IF approved THEN publish_content, emit ApprovalGranted
        IF denied THEN suppress_content, emit ApprovalDenied
```

**Rationale:** Governance gate. Moderate anomalies (likely legitimate) require confirmation.

**Implementation:**
- Compute severity in detector.rs
- Route to approval endpoint
- Block publish on ApprovalDenied

---

### Policy: MarketVision-BlockCriticalCompromise
**Rule:** If severity > 8 (compromise signal), suppress and require 2FA override.

```
IF severity > 8
   AND anomaly_type = CompromiseSignal
   THEN decision = SUPPRESS
        emit security_alert_to_creator
        require_2fa_confirmation()
        IF 2fa_verified THEN publish (mark as override)
        IF 2fa_timeout THEN delete_content
```

**Rationale:** Account security. Critical compromise signals (3+ indicators) = likely bot/attacker.

**Implementation:**
- Emit `SecurityAlertRequested` event
- Route to creator's registered 2FA device (SMS/TOTP)
- Confirm via `/api/capsules/market_vision/confirm_2fa`

---

### Policy: MarketVision-SubscriberNotification
**Rule:** If severity ≥ 8 AND subscriber agreement > 70%, notify subscribers.

```
IF severity >= 8
   AND subscriber_consensus.agreement > 0.7
   AND subscriber.anomaly_alert_preference = "opt_in"
   THEN emit subscriber_notification
```

**Rationale:** Transparency. High-severity, unexpected anomalies warrant subscriber awareness.

**Implementation:**
- Emit `AnomalyNotificationRequested` event
- Route to feedback router (subscriber preference honored)

---

### Policy: MarketVision-ConsensusBoost
**Rule:** If subscriber agreement is high, boost anomaly severity by 1–2 points.

```
IF subscriber_consensus.agreement > 0.7
   THEN severity += 1
        confidence = (confidence + agreement) / 2.0
   rationale = "Subscribers expect predictable behavior; deviation = higher risk"
```

**Rationale:** Consensus amplification. If 80% of subscribers expect creator's normal voice, deviation is more anomalous.

**Implementation:**
- After severity calculation, check `creator_profile.subscriber_consensus.agreement`
- Boost severity if > 0.7
- Emit `SeverityBoosted` event (logged for transparency)

---

### Policy: MarketVision-BypassOption
**Rule:** Creator can disable anomaly detection for specific content (e.g., personal essays).

```
IF content.bypass_anomaly_detection = true
   AND creator.tier >= 2  // Only tier 2+ can bypass
   THEN skip_anomaly_detection()
        emit event: "AnomalyDetectionBypassed (reason: creator_override)"
```

**Rationale:** Creator autonomy. Sensitive topics (personal, experimental) may legitimately deviate.

**Implementation:**
- Check flag in content metadata
- Verify creator tier has override permission
- Emit event for audit trail

---

### Policy: MarketVision-ProfileUpdate
**Rule:** Creator profile baseline updated every 100 posts or weekly (whichever first).

```
IF creator.posts_since_last_update >= 100
   OR created_at + 7 days < now()
   THEN recompute_profile_from_last_500_posts()
        update_baseline_statistics()
        emit ProfileUpdated event
        notify_creator_of_new_profile()
```

**Rationale:** Drift tracking. Creator's voice evolves; baseline should reflect current state.

**Implementation:**
- Cron job: daily check for update triggers
- Fetch last 500 posts from immutable event log
- Recalculate all features (sentiment, formality, vocabulary, timing)
- Update `creator_profile` table

---

## Part 2: Policy Evaluation Framework

### Standard Policy Decision

All policies follow this standard evaluation:

```rust
pub enum PolicyDecision {
    ALLOW,
    DENY,
    REQUIRE_APPROVAL,  // Blocks action, waits for creator confirmation
    SUPPRESS,          // Blocks action, requires 2FA override
    LOG_ONLY,          // Permits action, logs event for audit
}

async fn check_policy(
    &self,
    creator_id: Uuid,
    action: &str,
    context: &PolicyContext,  // Content, timing, engagement, etc.
) -> Result<PolicyDecision> {
    // 1. Evaluate ReBAC policies (siss-gatekeeper)
    let rebac_decision = self.gatekeeper.evaluate(&policy_request).await?;
    
    // 2. Evaluate capsule-specific policies
    let capsule_decision = match action {
        "rollback" => self.check_24h_window(&context),
        "revoke" => self.check_1h_deadline(&context),
        "publish" if market_vision => self.check_anomaly_severity(&context),
        _ => PolicyDecision::LOG_ONLY,
    };
    
    // 3. Combine decisions (fail-closed: deny wins)
    combine_decisions(rebac_decision, capsule_decision)
}
```

### Approval Gate Workflow

When decision = `REQUIRE_APPROVAL`:

```
1. Emit ApprovalRequested event
2. Route to creator via feedback router
3. Create approval_request record (UUID, timeout=5 mins, context)
4. Block publish on wait_for_approval() future
5. Creator responds via `/api/capsules/{id}/approve` or timeout
6. Emit ApprovalGranted or ApprovalDenied
7. Unblock publish (or clean up on denial)
```

---

## Part 3: Pricing Model

### Per-Capsule Pricing

| Capsule | Monthly | Annual | Use Case | Target Market |
|---------|---------|--------|----------|----------------|
| **AntiYou** | €2 | €24 | Regret tracking + rollback | Individual creators, risk-averse publishers |
| **TimeCapsule** | €3 | €36 | Scheduled publishing | Newsletter creators, content planners |
| **Market Vision** | €5 | €60 | Anomaly detection | High-profile creators, account security |
| **Bundle (all 3)** | €8/mo | €96/yr | Complete governance suite | Premium creators (50% discount vs. ala carte) |

### Revenue Projections (3-Year Horizon)

**Year 1 (Q3 2026–Q2 2027): Market Entry**
```
Target: 1K creators
AntiYou adoption:      50% = 500 creators × €2 = €1,000/mo = €12K/yr
TimeCapsule adoption:  70% = 700 creators × €3 = €2,100/mo = €25.2K/yr
Market Vision adoption: 30% = 300 creators × €5 = €1,500/mo = €18K/yr
Bundle adoption:       50% = 500 creators × €8 = €4,000/mo = €48K/yr
──────────────────────────────────────────────────
Year 1 ARR: €103.2K (conservative, low cross-sell)
```

**Year 2 (Q3 2027–Q2 2028): Scaling**
```
Target: 5K creators
AntiYou adoption:      40% = 2K creators × €2 = €4,000/mo = €48K/yr
TimeCapsule adoption:  60% = 3K creators × €3 = €9,000/mo = €108K/yr
Market Vision adoption: 40% = 2K creators × €5 = €10,000/mo = €120K/yr
Bundle adoption:       50% = 2.5K creators × €8 = €20,000/mo = €240K/yr
──────────────────────────────────────────────────
Year 2 ARR: €516K (scaling, improved cross-sell)
```

**Year 3 (Q3 2028–Q2 2029): Expansion**
```
Target: 10K creators (stretch goal)
AntiYou adoption:      40% = 4K creators × €2 = €8,000/mo = €96K/yr
TimeCapsule adoption:  60% = 6K creators × €3 = €18,000/mo = €216K/yr
Market Vision adoption: 40% = 4K creators × €5 = €20,000/mo = €240K/yr
Bundle adoption:       50% = 5K creators × €8 = €40,000/mo = €480K/yr
──────────────────────────────────────────────────
Year 3 ARR: €1.032M (growth trajectory toward €3M)
```

### Path to €3M ARR

€3M target requires either:

**Option A: Scale to 30K creators at €30/creator/mo average**
```
30K creators × €30/mo × 12 = €10.8M ARR (exceeds target)
Requires: 3x larger creator base than Year 3 projection
Timeline: Q1–Q2 2029 (aggressive)
```

**Option B: Premium tier adoption at 10K creators**
```
10K creators with:
  - 60% premium (€5/mo avg, multiple capsules): 6K × €60/yr = €360K
  - 40% standard (€2/mo avg, single capsule): 4K × €24/yr = €96K
  Total: €456K (still below €3M)

To reach €3M at 10K creators requires €300/year per creator
  = €25/month average (bundle pricing + premium upsells)
  = 75% bundle adoption + 50% cross-sell multiplier
  Realistic 2029 target: €500K–€1M ARR (depends on market conditions)
```

**Option C: Geographic Expansion + Partner Bundling**
```
Primary market (EU): 10K creators × €30/mo = €3.6M ARR
Secondary markets (APAC, Americas): Add 15K creators × €15/mo = €2.7M ARR
Partner bundles (Substack, Medium, etc.): +€500K–€1M in revenue share
───────────────────────────────────────
Total: €6.8M–€7.8M ARR by 2030
Realistic 2027 target: €500K–€1M from EU market
```

### Pricing Strategy

**Bundle Incentive (Recommended):**
- Ala carte: €2 + €3 + €5 = €10/mo
- Bundle: €8/mo
- Savings: 20% discount encourages adoption

**Tier-Based Pricing (Future):**
```
Creator Tiers:
  Tier 1 (0–1K subscribers):    €8/mo (bundle)
  Tier 2 (1K–10K subscribers):  €15/mo (premium bundle + priority support)
  Tier 3 (10K+ subscribers):    €30/mo (white-label + custom policies)
```

**Volume Discounts:**
```
1–10 creators:   full price
11–50 creators:  10% discount
51–100 creators: 20% discount
100+ creators:   custom pricing (enterprise)
```

---

## Part 4: Financial Model Assumptions

| Assumption | Value | Rationale |
|------------|-------|-----------|
| CAC (Customer Acquisition Cost) | €500 | Content marketing + partnerships |
| CAC payback period | <16 months | Industry standard: <12 months |
| LTV (Lifetime Value) | €720 | €30/mo × 24 months avg subscription |
| Churn rate (monthly) | 5% | SaaS standard; retention programs can reduce to 3% |
| Cross-sell rate | 50% | 50% of customers adopt ≥2 capsules |
| Net revenue retention (NRR) | 110% | Expansion revenue from upsells |
| Market TAM | €50M+ | Creator platform market at 500K+ creators |
| Serviceable SAM | €5M | Attainable at 10K creators in EU |
| SOM (Serviceable Obtainable) | €1M–€3M | Realistic 2027–2029 |

---

## Part 5: Competitive Positioning

| Competitor | AntiYou | TimeCapsule | Market Vision | Pricing |
|------------|---------|-------------|---------------|---------|
| **SovereignNexus (us)** | ✅ 24h rollback | ✅ Scheduled + conditional | ✅ Anomaly detection | €8/mo bundle |
| Twitter/X | ❌ | ❌ | Limited (ML) | Free (ads) |
| Substack | ⚠️ Delete only | ❌ | ❌ | Free (takes 10%) |
| Medium | ❌ | ✅ Scheduled | ❌ | Free (freemium) |
| Ghost | ✅ Drafts only | ✅ Scheduled | ❌ | €25/mo (all-in) |
| LinkedIn | ❌ | ✅ Scheduled | Limited | Free (ads) |

**Competitive Advantage:**
- **AntiYou:** 24h rollback is unique; competitors delete only (permanent)
- **TimeCapsule:** Conditional delivery + recurrence + revocation deadline (only platform)
- **Market Vision:** Subscriber consensus + anomaly scoring (only ML-powered governance)
- **Bundle:** €8/mo for all 3 = €1/mo per feature (underpriced vs. Ghost €25/mo)

---

## Part 6: GDPR & Data Retention

All policies adhere to GDPR Article 17 (Right to Erasure):

### Data Classification

| Data Type | Retention | Erasure | Notes |
|-----------|-----------|---------|-------|
| **Snapshots** | 24h–7d | Immediate (creator delete) | AntiYou, TimeCapsule, MarketVision snapshots |
| **Events** | Permanent | Permanent (append-only, cryptographic proof) | Immutable audit trail |
| **Creator Profile** | Active | Delete on creator erasure | MarketVision baseline, subscriber consensus |
| **Anomaly Signals** | 90d | Delete after 90d or on erasure | Signal history for analysis |

### Erasure Flow

```
Creator initiates: DELETE /api/account/erase
System:
  1. Emit: AccountErasureRequested event (signed, timestamps)
  2. Delete: All snapshots (anti_you_records.content_snapshot, etc.)
  3. Delete: CreatorProfile, AnomalySignals
  4. Retain: immutable_events table (cannot delete, constitutional audit trail)
  5. Anonymize: creator_id → UUID(null) in retained events
  6. Respond: GDPR deletion confirmation + proof (Merkle root of final state)
```

---

## Part 7: Governance Authority & Change Control

**Locked Status:** CONSTITUTIONAL
- Policies defined herein cannot be changed without explicit approval
- Series A investor sign-off required for pricing changes
- Engineering lead approval required for policy modifications
- Quarterly review gate (Sep 30, Dec 31, Mar 31, Jun 30)

**Change Request Process:**
1. Propose change with rationale
2. Impact analysis (affected creators, revenue implications)
3. Governance review (engineering + finance + legal)
4. User notification (30 days advance notice for adverse changes)
5. Implementation (only after approval + notification)

---

## Sign-Off

**Specification locked by:** Andrei Leukhin (Engineering Lead)  
**Finance approved by:** [CFO/Finance Lead]  
**Series A authority:** [Investor]  
**Effective date:** Aug 1, 2026  
**Next review:** Sep 30, 2026  

---

END OF GOVERNANCE POLICIES & PRICING REFERENCE

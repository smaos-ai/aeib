# Operational Runbook — SovereignNexus Production
**Effective Date:** July 1, 2026  
**Status:** ACTIVE  
**Prepared by:** Palantir-Finalization-Night12  
**Last Updated:** 2026-05-27

---

## Executive Summary

This runbook defines 24/7 monitoring procedures, incident response playbooks, escalation matrices, and post-incident procedures for SovereignNexus production operations. All ops teams must memorize the escalation criteria and response windows (P1: 0–15 min, P2: 15–60 min, P3: 60+ min).

---

## 24/7 MONITORING PROCEDURES

### Monitoring Stack

**Primary Tools:**
- **Datadog:** Real-time metrics, dashboards, alerting
- **PagerDuty:** On-call scheduling, escalation, incident coordination
- **Splunk:** Log aggregation, search, alerting
- **StatusPage.io:** Public status updates (if needed)

**Monitored Endpoints (All Regions):**
- Prague API gateway (primary customer endpoint)
- Frankfurt API gateway (secondary customer endpoint)
- London API gateway (tertiary customer endpoint)
- Health check endpoints (all 3 regions, every 10 seconds)

---

### Hourly Monitoring Checklist (Ownership: On-Call Engineer)

**Every hour, at :00 UTC (or :00 local time per region):**

```
09:00 UTC Check:
- [ ] API latency (p50, p95, p99): verify trending stable
  - Prague: target <80ms p95
  - Frankfurt: target <80ms p95
  - London: target <90ms p95
- [ ] Error rate per customer: should be <0.1%
  - Prague: [X]% (alert if >0.5%)
  - Frankfurt: [X]% (alert if >0.5%)
  - London: [X]% (alert if >0.5%)
- [ ] Capsule tier health (all 5 tiers):
  - Tier 1 (Computation): CPU <80%, memory <75%
  - Tier 2 (Graph indexing): index size <2TB, query time <100ms
  - Tier 3 (Policy enforcement): throughput >10k req/s capacity, current load <50%
  - Tier 4 (Feedback routing): queue depth <1000, processing latency <500ms
  - Tier 5 (Agent shell): active agents <500 (headroom to 1000)
- [ ] Database replication lag (all regions):
  - Prague → Frankfurt: <5s
  - Frankfurt → London: <5s
  - Secondary check: Prague → London (direct): <10s
- [ ] Memory/disk utilization:
  - All nodes: memory <80%
  - All nodes: disk <75%
  - Logs: being rotated and not filling disk
- [ ] Network metrics:
  - Inter-region latency: stable (Prague-Frankfurt <10ms, Frankfurt-London <20ms)
  - Packet loss: <0.01%
  - Bandwidth saturation: <50% of capacity
- [ ] PagerDuty alerts queue: all acknowledged or resolved
- [ ] No P1/P2 incidents from previous hour still open?
```

**If any check fails:**
- Investigate immediately (5–10 min)
- Escalate to L2 if can't determine root cause
- Log in incident tracking system
- Notify war room (if active)

---

### Daily Metrics Review (Ownership: Ops Lead) — 09:00 UTC Each Morning

**Daily standup call (15 minutes, all ops/on-call team):**

```
DAILY METRICS REVIEW — [DATE]
---

1. Overnight Summary (5 min)
   - Any incidents (P1/P2/P3)? [list or "none"]
   - Total uptime overnight: [%]
   - Any alerts that fired: [list]
   - Any near-miss scenarios: [explain]

2. Metrics Trending (5 min)
   - API latency: trend over last 24h (target: stable or decreasing)
   - Error rate: trend over last 24h (target: <0.1%, ideally decreasing)
   - Customer load: trend over last 7 days (expected to be stable for Week 1)
   - Capsule tier performance: any degradation? [explain if yes]

3. Upcoming Focus Areas (3 min)
   - Any scheduled maintenance today?
   - Expected customer load changes?
   - Monitoring rule updates planned?
   - On-call coverage changes?

4. Action Items (2 min)
   - RCA follow-ups from previous incidents
   - Monitoring improvements
   - Documentation updates
```

**Post-standup:** Ops lead sends email summary to team + leadership

---

### Weekly Operations Review (Ownership: Ops Lead) — Every Monday, 10:00 UTC

**Agenda (1 hour):**

1. **Weekly Uptime/Performance (10 min)**
   - Uptime %: target ≥99.95%
   - Avg latency (p95): target <100ms per customer
   - Error rate: target <0.1%
   - SLA credit calculations (if applicable)

2. **Incident Summary (15 min)**
   - Total incidents (P1/P2/P3)
   - Most significant incident (RCA + action items)
   - Trends: are we seeing patterns?
   - Alert tuning: any false positives or missed alerts?

3. **Metrics & Trends (10 min)**
   - Customer load growth (expected: steady for first month)
   - Peak concurrency: when and why?
   - Resource utilization: approaching any limits?
   - Cost per transaction: tracking toward target?

4. **Roadmap & Improvements (15 min)**
   - Planned monitoring improvements (next 2 weeks)
   - Upcoming maintenance windows
   - Scaling plans (if needed)
   - Training needs (incident response, new procedures)

5. **Cross-Functional Sync (10 min)**
   - Engineering: any deployments planned?
   - Customer Success: any customer feedback on reliability?
   - Product: any feature rollouts affecting infrastructure?

---

## INCIDENT RESPONSE PLAYBOOK

### Severity Definitions & Response Targets

| Severity | Criteria | Response Time | Resolution Target | Escalation |
|----------|----------|----------------|-------------------|-----------|
| **P1 (Critical)** | API down OR error rate >5% OR latency >500ms for >1 min | <5 min (page) | <30 min | → L2 immediately, → CTO if not resolved in 10 min |
| **P2 (High)** | Latency 150–500ms OR error rate 0.5–5% OR 1 customer degraded | <15 min | <60 min | → L2 on-call, → Ops lead if not progressing |
| **P3 (Medium)** | Latency spike <150ms OR error rate <0.5% OR minor issue | <60 min | <4 hours or next business day | → L1 support, → L2 if pattern emerges |
| **P4 (Low)** | Documentation issue, feature request, cosmetic bug | <24 hours | <1 week | → L1 support queue |

---

### P1 Incident Response (Critical, 0–15 min)

**Trigger Conditions:**
- API endpoint returns 500+ errors (>50% requests failing)
- Response latency >500ms for >1 minute across >1 customer
- Database completely unreachable (replication down)
- Capsule Tier 1 (computation) offline or severely degraded
- Security incident (data breach, unauthorized access)

**Immediate Actions (T+0–2 min: Detection & Page)**
- [ ] Alert fires in Datadog → automatic PagerDuty page
- [ ] On-call engineer receives page (phone, SMS, app)
- [ ] On-call engineer responds in PagerDuty: "Acknowledged" + ETA to investigate
- [ ] War room Slack channel created: #prod-incidents-[date]-[time]
- [ ] Ops lead, L2 engineer, Customer Success pinged in channel: "P1 INCIDENT - need immediate investigation"

**T+2–5 min: Initial Investigation**
- [ ] On-call engineer SSHs into production environment
- [ ] Checks:
  - Is API endpoint responding? (curl /health)
  - Are all Capsule tiers online? (Datadog, health endpoints)
  - Is database reachable and replicating? (query log, replication lag)
  - Are there recent deployments? (check git log, deployment status)
  - Are there any spike in error logs? (Splunk query, tail -f)
  - Is customer traffic normal or spiked? (check load metrics)
- [ ] Captures current state:
  - Screenshot of Datadog dashboards (latency, error rate, CPU, memory)
  - Copy of last 100 error log lines (Splunk export)
  - Recent deployment info (Docker image, deployment time)
- [ ] Posts findings to war room: "Initial findings: [root cause hypothesis]"

**T+5–10 min: Diagnosis & Mitigation Decision**

**If root cause identified (e.g., "Tier 1 OOM due to memory leak"):**
- [ ] Propose mitigation: "Restart Tier 1 services" or "Rollback deployment" or "Scale horizontally"
- [ ] CTO approves (if available) or ops lead approves
- [ ] Execute mitigation:
  - **Restart:** Kill pods, let Kubernetes restart (takes ~30s)
  - **Rollback:** kubectl rollout undo deployment/[tier], verify health (takes ~1 min)
  - **Scale:** kubectl scale deployment/[tier] --replicas=5, monitor recovery (takes ~1 min)
- [ ] Monitor recovery: latency should drop within 30s–1 min
- [ ] Confirm API responding: "API is recovering. Latency [Xms]. Error rate [Y]%. Expected full recovery in 2–3 min."

**If root cause unclear (e.g., "Network partition? Database issue?"):**
- [ ] Escalate to CTO immediately (phone call)
- [ ] CTO joins war room Slack + provides guidance
- [ ] Possible next steps: failover to secondary region, rollback, investigate further
- [ ] War room log updated: "Escalated to CTO. Investigating [specific hypothesis]."

**T+10–15 min: Verification & Customer Communication**

- [ ] Verify API is fully recovered:
  - Latency: <100ms (p95)
  - Error rate: <0.1%
  - All customer endpoints responding
- [ ] Send customer notification:
  - Email to all 3 customers: "INCIDENT RESOLVED: We experienced a brief outage lasting [X minutes]. Root cause: [brief description]. All systems now operational."
  - Timestamp: [T+13 min from incident start]
  - Include: root cause summary + prevention plan (if known)

**T+15+ min: RCA Initiation & Follow-Up**
- [ ] Create RCA document (Google Doc): link posted to war room
- [ ] Assign RCA owner (on-call engineer)
- [ ] RCA due date: next morning (within 24h)
- [ ] Standup scheduled: next day 09:00 UTC (RCA review + action items)

---

### P2 Incident Response (High, 15–60 min)

**Trigger Conditions:**
- Latency spikes between 150–500ms for >2 min
- Error rate 0.5–5% sustained for >1 min
- One customer experiencing issues (latency spike, errors, or degradation)
- Database replication lagging >10s (but not down)
- Capsule tier degraded but not offline (high CPU/memory, slow responses)

**Response Flow (T+0–15 min):**

- [ ] PagerDuty alert fires → on-call engineer paged (not automatic escalation to CTO)
- [ ] On-call engineer acknowledges: "Investigating now"
- [ ] Checks (similar to P1, but more methodical):
  - Specific customer affected? (check customer-specific latency)
  - Which Capsule tier(s) involved? (check metrics)
  - Recent deployments or config changes? (check git log, runbooks)
  - Load spike (legitimate or abuse)? (check request patterns)
- [ ] Posts initial findings to war room (Slack: #prod-incidents)
- [ ] Customer Success notifies affected customer: "We've identified a latency issue affecting your service. Our team is investigating. ETA for update: 15 minutes."

**Resolution (T+15–45 min):**

- [ ] If root cause found:
  - Temporary mitigation: auto-scale, rate limit abuse traffic, restart degraded service
  - Verification: latency should drop within 5–10 min
  - Permanent fix: scoped and planned (but not necessarily implemented immediately)
- [ ] If not resolved by T+30 min:
  - Escalate to Ops lead (phone call)
  - Ops lead reviews investigation, considers escalation to L2 engineering
  - If escalating: page L2 on-call engineer from PagerDuty
  - L2 joins war room, brings deeper technical expertise

**Customer Communication (T+45 min):**

- [ ] Update customer: "We've identified and resolved the latency issue. Services are returning to normal. Detailed RCA will follow within 24 hours."
- [ ] Continue monitoring: ensure issue doesn't recur

**Follow-Up (T+60+ min):**

- [ ] RCA started: due within 48h
- [ ] Monitoring rule review: did we catch this early enough? Can we improve alerting?
- [ ] Action items: permanent fix prioritized based on severity/impact

---

### P3 Incident Response (Medium, 60+ min)

**Trigger Conditions:**
- Minor latency spike (<150ms above baseline, <1 min duration)
- Error rate <0.5% but sustained
- Single transaction failure (not affecting customer operations)
- Degraded feature (non-critical path, no customer reported impact)
- Documentation/knowledge base issue

**Response Flow:**

- [ ] Logged in incident tracking system (Jira or similar)
- [ ] Assigned to on-call engineer (lower priority than P1/P2)
- [ ] Investigated during business hours (next day)
- [ ] No immediate escalation unless pattern detected
- [ ] If pattern emerges (e.g., 3+ similar P3s in 24h):
  - Promote to P2 or P1
  - Escalate to L2 engineering

**Example P3s:**
- Temporary spike in webhook processing latency (caused by legitimate load increase)
- Intermittent timeout in audit trail logging (doesn't affect primary API)
- Missing error message in customer-facing API response (documentation correction needed)

---

## ESCALATION MATRIX & CONTACTS

### On-Call Schedule (24/7 Coverage, Jul 1–31)

**Primary On-Call: Ops Engineer** (24h rotation)
- Responsible for: First response to all alerts, investigation, triage
- Page method: PagerDuty (SMS + phone call + app notification)
- Response window: <5 min for P1, <15 min for P2

**Secondary On-Call: L2 Engineer** (24h rotation, weekdays + emergencies)
- Responsible for: Deep technical debugging, deployments, rollbacks
- Activation: On-call ops escalates (P1 if not resolved in 10 min, P2 if not resolved in 45 min)
- Response window: <10 min for escalation, <30 min for investigation

**Tertiary Escalation: CTO** (24h on-call, critical only)
- Responsible for: Governance decisions, critical incident coordination, customer comms
- Activation: Only if P1 not resolved in 15 min or significant business impact
- Response window: <15 min (phone call)

**Customer Success Escalation:** (Business hours primary, on-call after hours)
- Responsible for: Customer communication, status updates, post-incident check-in
- Activation: Ops lead initiates if any P1/P2 affecting customers
- Communication channel: Email + phone call to customer primary contact

---

### Escalation Decision Tree

```
INCIDENT DETECTED
    ↓
[Is it P1? Error rate >5% OR latency >500ms OR API down]
    ├─ YES → P1 Response (T+0–15 min)
    │  ├─ T+10 min: Can L1 fix? YES → Resolve, document RCA
    │  ├─ T+10 min: Can L1 fix? NO → Escalate to CTO immediately
    │  └─ T+15 min: If still ongoing → Declare critical, activate incident commander
    └─ NO → Continue below

[Is it P2? Latency 150–500ms OR error rate 0.5–5%]
    ├─ YES → P2 Response (T+0–60 min)
    │  ├─ T+30 min: Can L1 fix? YES → Resolve
    │  ├─ T+30 min: Can L1 fix? NO → Escalate to L2 engineering
    │  └─ T+45 min: No progress? → Escalate to Ops lead + CTO for guidance
    └─ NO → Continue below

[Is it P3? Minor issues, non-critical]
    ├─ YES → P3 Response
    │  ├─ Log in tracking system
    │  ├─ Investigate during business hours
    │  └─ If pattern: promote to P2
    └─ NO → Feature request / documentation (P4)
```

---

### Contact Information (On-Call Roster)

**Jul 1–7, 2026:**

| Role | Name | Phone | Email | Slack | Notes |
|------|------|-------|-------|-------|-------|
| **Ops (Primary)** | [Name A] | +41-XXXX-XXXX | [email] | @ops-lead | Mon-Sun, 24h |
| **L2 Engineer** | [Name B] | +41-XXXX-XXXX | [email] | @l2-engineer | Mon-Fri, 06:00–22:00 UTC |
| **CTO (Critical)** | [Name C] | +41-XXXX-XXXX | [email] | @cto | 24/7 (emergencies only) |
| **Customer Success** | [Name D] | +41-XXXX-XXXX | [email] | @customer-ops | Mon-Fri, 08:00–18:00 UTC |

**Backup contacts (if primary unavailable):**
- Ops backup: [Name E]
- L2 backup: [Name F]
- CTO backup: [Name G] (for extended outages)

**Update on-call roster every Sunday (rotate weekly).**

---

## INCIDENT RESPONSE PROCEDURES (Step-by-Step)

### Step 1: Alert Fires → Acknowledgment (0–2 min)

**On-Call Engineer:**
```
WHEN: PagerDuty alert fires (SMS + phone call)
WHAT: Acknowledge immediately in PagerDuty
HOW:
  1. Open PagerDuty app or website
  2. Find the alert
  3. Click "Acknowledge" (not "Resolve")
  4. Set status: "Investigating"
  5. ETA: "5 minutes to initial findings"
TIMELINE: Do this within 2 minutes of alert firing
NOTIFY: If you don't have PagerDuty access, call ops lead immediately
```

---

### Step 2: Initial Investigation (2–5 min)

**On-Call Engineer:**
```
WHAT: Gather facts about what's happening
HOW:
  1. Open Datadog dashboard: https://app.datadoghq.com
  2. Check:
     - API latency (p50, p95, p99): is it elevated?
     - Error rate: is it >0.1% or higher?
     - Request throughput: is it normal or spiked?
  3. Check per-region:
     - Prague endpoint health
     - Frankfurt endpoint health
     - London endpoint health
  4. Check Capsule tiers:
     - Are all 5 tiers online?
     - CPU/memory: any spikes?
     - Are there any deployment rollouts in progress?
  5. Check Splunk logs:
     - Search: "ERROR" or "Exception" (last 5 min)
     - Copy representative error message
  6. Check recent deployments:
     - Any deploy in last 15 minutes?
     - Any config changes?
  7. Take screenshots: Datadog dashboards + Splunk errors (for RCA)
TIMELINE: 3–5 minutes total
OUTPUT: Create incident in PagerDuty with initial findings
```

---

### Step 3: Root Cause Hypothesis (5–10 min)

**On-Call Engineer:**
```
WHAT: Determine what's likely causing the issue
HYPOTHESIS:
  - "Capsule Tier 1 out of memory → OOM killed processes → API errors"
  - "Recent deployment has a bug → causing latency spikes"
  - "Database replication lag → slow queries → API timeouts"
  - "Customer traffic spike → hitting rate limit → API returning 429s"
  - "Network partition between Prague and Frankfurt → replication lag"
  - "Security event: DDoS attack → overwhelming API gateway"
EVIDENCE: Use metrics + logs to support hypothesis
VERIFICATION:
  - If memory issue: check Datadog memory graphs
  - If deployment issue: check git log for recent changes
  - If database issue: check replication lag metric
  - If traffic spike: check requests per second graph
  - If network: check ping times between regions
TIMELINE: 5–10 min (post investigation)
OUTPUT: Post hypothesis to war room Slack: "Probable cause: [X]. Evidence: [Y]"
```

---

### Step 4: Mitigation Decision (10–15 min)

**On-Call Engineer (+ CTO if escalated):**
```
IF root cause is clear AND mitigation is safe:
  1. Propose mitigation: "Restart Tier 1" or "Rollback deployment" or "Scale up"
  2. If CTO available: get approval (Slack or phone)
  3. If CTO unavailable: ops lead can approve P1 mitigations
  4. Execute mitigation (see below)
  5. Monitor recovery: latency/error rate should improve within 1–2 min

IF root cause is unclear:
  1. Page CTO immediately (phone call)
  2. Provide: incident timeline, investigation findings, current status
  3. CTO guidance: continue investigating, rollback, failover, etc.
  4. Follow CTO's decision

MITIGATION OPTIONS:
  A. Restart service: kubectl delete pod [pod-name] (takes ~30s)
  B. Rollback deployment: kubectl rollout undo [deployment] (takes ~1 min)
  C. Scale horizontally: kubectl scale deployment/[tier] --replicas=10 (takes ~1 min)
  D. Failover region: switch traffic from Prague to Frankfurt (takes ~2 min)
```

---

### Step 5: Verification (15–20 min)

**On-Call Engineer:**
```
VERIFICATION CHECKLIST:
  [ ] API /health endpoint responding (200 OK)
  [ ] Latency back to baseline (<100ms p95)
  [ ] Error rate back to <0.1%
  [ ] All 3 customer endpoints responding
  [ ] All Capsule tiers online and healthy
  [ ] Database replication lag normal (<5s)
  [ ] No new errors in logs (Splunk)
  [ ] Request throughput back to baseline

IF all checks pass:
  → Incident is resolved
  → Proceed to Step 6 (Customer Communication)

IF checks don't pass:
  → Mitigation didn't work as expected
  → Escalate to CTO + L2 engineering (if not already)
  → Try alternative mitigation or deeper investigation
```

---

### Step 6: Customer Communication (within 15 min of detection)

**Customer Success Lead:**
```
TIMING: Send first update within 15 minutes of incident start
FIRST UPDATE EMAIL:
  Subject: SovereignNexus Incident Update — [TIME UTC]
  Body:
    "Dear customers,
    We are currently investigating an issue affecting API performance.
    
    Issue: [Brief description, e.g., 'latency spike']
    Status: [In progress / identified / mitigating]
    ETA: [Expected resolution time, e.g., '10 minutes']
    
    Our team is actively working on this. We will update you every 15 minutes.
    
    Support: contact@sovereignnexus.eu or +41-XXXX-XXXX
    "

IF RESOLVED:
  Subject: SovereignNexus Incident Resolved — [TIME UTC]
  Body:
    "The incident has been resolved. All systems are now normal.
    
    Duration: [X minutes]
    Root cause: [Brief explanation]
    Impact: [Number of requests affected / customer impact]
    
    RCA: Full analysis will be available within 24 hours.
    
    Thank you for your patience."

IF NOT RESOLVED:
  Send update every 15 minutes with latest progress / ETA
```

---

### Step 7: RCA (Root Cause Analysis) — Due within 24 hours

**On-Call Engineer (or Ops Lead):**
```
RCA DOCUMENT OUTLINE:

1. INCIDENT SUMMARY
   - Title: [Brief description]
   - Date/Time: [When it started and ended]
   - Duration: [Total minutes down/degraded]
   - Customers Impacted: [Which customers affected]
   - Severity: [P1/P2/P3]

2. TIMELINE
   - T+0: What happened (first symptom)
   - T+X: What action was taken (investigation started)
   - T+Y: What was discovered (root cause identified)
   - T+Z: What was done (mitigation applied)
   - T+W: When was it resolved
   (Include timestamps for all entries)

3. ROOT CAUSE
   - What was the underlying issue?
   - Why did it happen?
   - Evidence supporting the root cause?

4. CONTRIBUTING FACTORS
   - What made this worse?
   - System limitations?
   - Process gaps?
   - (List 3–5 factors if applicable)

5. IMPACT ANALYSIS
   - How many customers affected?
   - How many transactions failed?
   - Did any data loss occur?
   - Customer financial impact (if any)

6. REMEDIATION
   - What was done to fix it?
   - Was it temporary or permanent?
   - Timeline for permanent fix (if applicable)

7. PREVENTION
   - How will we prevent this in the future?
   - Monitoring improvements?
   - Code changes needed?
   - Process changes?

8. ACTION ITEMS
   - Owner: _____, Task: [fix X], Due: [date], Status: [not started / in progress / done]
   - Owner: _____, Task: [improve monitoring for Y], Due: [date], Status: [pending]
   - (List all action items needed)

9. FOLLOW-UP
   - Next review date: [when to check on action items]
   - Stakeholders notified: [list]
   - Customer credit issued: [Y/N, if applicable amount]

REVIEW PROCESS:
  - On-call engineer drafts RCA (shared Google Doc)
  - Ops lead reviews and adds context
  - CTO reviews if critical incident
  - Engineering lead signs off (technical accuracy)
  - Shared with all customers affected
  - Posted to internal incident tracking system
```

---

### Step 8: Post-Incident Review (within 48 hours)

**Team (Ops + Engineering + Customer Success):**
```
TIMING: Schedule within 24 hours of incident resolution
DURATION: 30–45 minutes
ATTENDEES: On-call ops, L2 engineer, Ops lead, CTO (if critical)

AGENDA:
  1. Review RCA findings (5 min)
  2. Discuss response: what went well? (5 min)
  3. Discuss response: what could improve? (5 min)
  4. Discuss prevention: are action items sufficient? (10 min)
  5. Discuss communication: customer satisfaction? (5 min)
  6. Approval: RCA is complete and shared? (5 min)

OUTCOMES:
  - Action items refined and prioritized
  - Monitoring improvements planned
  - Team training needs identified
  - Customer follow-up scheduled (if needed)
  - Document filed in incident tracking system
```

---

## POST-INCIDENT PROCEDURES

### Root Cause Analysis (RCA) Template

**Incident RCA: [Title]**  
**Date:** [Incident date] | **Duration:** [X minutes] | **Severity:** [P1/P2/P3]

**Executive Summary:**
[1–2 sentence overview of what happened and how long it took to resolve]

**Timeline:**

| Time (UTC) | Event | Action |
|-----------|-------|--------|
| 08:15:30 | API latency spike to 500ms | PagerDuty alert fired |
| 08:15:45 | On-call engineer acknowledged | Began investigation |
| 08:18:00 | Identified Tier 1 memory issue | Confirmed OOM in logs |
| 08:19:30 | Restarted Tier 1 service | Mitigation applied |
| 08:21:00 | API latency returned to <100ms | Incident resolved |
| 08:21:15 | Customer notified of resolution | Status update sent |

**Root Cause:**
[Detailed explanation. Example: "Capsule Tier 1 experienced memory leak in agent coordination loop. Memory usage grew from 3GB (normal) to 7.5GB (limit) over 2 hours, causing OOM killer to terminate worker processes. This reduced compute capacity by 50%, causing API requests to queue and timeout."]

**Contributing Factors:**
1. [Memory monitoring alert threshold was set too high (8GB). Should have alerted at 6GB.]
2. [No memory profiling in agent coordination loop. Developers unaware of leak risk.]
3. [Deployment 3 days prior introduced new agent feature without memory tests.]
4. [No resource isolation between Tier 1 services. One app's leak affected all.]

**Impact Analysis:**
- Customers affected: All 3 (Prague, Frankfurt, London)
- Requests affected: ~2,000 (out of 8,000 during spike)
- Transactions failed: 250 (3% failure rate at peak)
- Data loss: None (requests queued, not dropped)
- Customer reported issues: Prague Central Bank (1 complaint), German Regulator (routine notification only)

**Remediation:**
- **Immediate:** Restarted Tier 1 service (temporary fix)
- **Short-term (within 1 week):** Deploy memory profiling to identify leak
- **Medium-term (within 2 weeks):** Fix memory leak in agent coordination
- **Long-term (within 1 month):** Implement resource isolation between Tier 1 apps

**Prevention:**
1. Lower memory alert threshold from 8GB → 6GB (immediate)
2. Add memory profiling tests to CI/CD pipeline (within 1 week)
3. Implement OOM prediction alerting (within 2 weeks)
4. Add Kubernetes resource quotas per service (within 1 month)

**Action Items:**

| Owner | Task | Due Date | Status | Verification |
|-------|------|----------|--------|--------------|
| Engineering | Deploy memory profiling | Jul 5 | In progress | Memory leak identified, fix proposed |
| DevOps | Lower alert threshold | Jul 1 | Done ✓ | Verified in PagerDuty config |
| Engineering | Fix memory leak | Jul 10 | Not started | Code review + performance test |
| DevOps | Add OOM prediction | Jul 15 | Not started | Alert fires <5 min before OOM |
| DevOps | Resource quotas | Jul 20 | Not started | Quotas applied, no service restarts |

**Customer Communication:**

- **Initial notification (08:21 UTC):** Email to all 3 customers (status update, ETA)
- **Resolution notification (08:22 UTC):** Email with resolution details, RCA link, apology + credit offer
- **Follow-up (Jul 2):** Phone calls to Prague Central Bank + German Regulator (reassurance, Q&A)
- **SLA credit (issued Jul 2):** 5% of monthly fee to Prague Central Bank (due to 6-minute incident)

**Sign-Off:**
- Ops Lead: _________________ Date: _____
- CTO: _________________ Date: _____
- Engineering Lead: _________________ Date: _____

---

## MONITORING RULE TUNING

### Alert Threshold Calibration (Post-RCA)

**Goal:** Catch real issues early, minimize false positives.

**Thresholds (as of Jul 1, 2026):**

| Metric | Warning (P3) | High (P2) | Critical (P1) |
|--------|------------|---------|--------------|
| **API Latency (p95)** | >120ms | >150ms | >250ms |
| **API Latency (p99)** | >180ms | >250ms | >500ms |
| **Error Rate** | >0.2% | >0.5% | >5% |
| **Database Lag** | >3s | >8s | >30s |
| **Capsule Tier 1 CPU** | >70% | >85% | >95% |
| **Capsule Tier 1 Memory** | >65% | >80% | >90% |
| **HTTP 5xx Rate** | >0.1% | >0.5% | >5% |
| **Request Queue Depth** | >100 | >500 | >2000 |

**Review & Adjustment:**
- Baseline thresholds set based on Week 1 stable performance
- If >3 false positive alerts in 24h: raise threshold by 10%
- If real incidents slip past monitoring: lower threshold by 10%
- Weekly review (every Monday) to assess accuracy

---

## RUNBOOK MAINTENANCE

### Weekly Updates (Every Monday)

- [ ] Review incident count + severity distribution (any trends?)
- [ ] Review on-call feedback (any procedural gaps?)
- [ ] Check contact information currency (any phone/email changes?)
- [ ] Verify all Slack channels are active and monitored
- [ ] Test PagerDuty escalation (simulate P1 alert)

### Monthly Comprehensive Review (First Monday of each month)

- [ ] Review all RCAs from previous month
- [ ] Identify systemic issues (are we fixing root causes or just symptoms?)
- [ ] Update monitoring thresholds based on incident patterns
- [ ] Review team training needs
- [ ] Update this runbook with lessons learned

### Quarterly Disaster Recovery Drills (Every 13 weeks)

- [ ] Simulate region failure (Prairie DR scenario)
- [ ] Test database restore from backup
- [ ] Verify failover procedures work
- [ ] Document any gaps
- [ ] Post-drill RCA and improvements

---

## Quick Reference Cards

### P1 Quick Reference (Print & Post in War Room)

```
P1 INCIDENT (Critical)
─────────────────────────────────────────
Alert fires → Acknowledge immediately
↓
Investigate (2–5 min):
  • Datadog latency/error rate
  • Splunk error logs (recent)
  • Recent deployments (git log)
  • Capsule tier status

Hypothesis → Mitigation (5–10 min):
  • Restart tier (kubectl delete pod)
  • Rollback (kubectl rollout undo)
  • Scale up (kubectl scale)

Verify recovery (1–2 min)
↓
Customer notification (<15 min)
↓
Escalate if not resolved in 10 min (CTO)
↓
RCA due within 24 hours
```

### P2 Quick Reference (Print & Post in War Room)

```
P2 INCIDENT (High Priority)
──────────────────────────────────────────
Alert fires → Acknowledge (2 min)
↓
Investigate methodically (5–10 min):
  • Identify affected customer
  • Check which systems involved
  • Rule out recent changes

Root cause → Mitigation (10–30 min):
  • Apply temporary fix
  • Scale/restart as needed

Verify (2–3 min)
↓
Customer notification (15 min mark)
↓
If not resolved in 45 min → Escalate to L2 engineering
↓
RCA due within 48 hours
```

---

**Document Status:** ACTIVE  
**Last Tested:** [Drill date if scheduled]  
**Next Review:** Every Monday at 09:00 UTC  
**Escalation Authority:** CTO has final say on critical decisions  

*Prepared by Palantir-Finalization-Night12. Execution transferred to Ops team on Jul 1, 06:00 UTC.*


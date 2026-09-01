# PILOT EXECUTION SUPPORT PLAYBOOK
## On-Call Runbook, Incident Response, Escalation Procedures (Nov-Dec 2026)

---

## EXECUTIVE SUMMARY
On-call engineer (you) provides 24/7 support for 3 production pilots. P1 incidents resolved <30 min, P2 <4h. Post-mortem + AP2 ledger documentation required for all incidents.

**On-Call Schedule:**
- Nov 1 - Dec 26: You (24/7 pager)
- Dec 27 - Dec 31: Series A hire (if available) or you (backup)
- Jan 1+: Transition to Series A team

**Contact:** Your phone (SMS pager), Slack #pilots-incident, email escalation@sovereignexus.com

---

## SUPPORT HIERARCHY (ESCALATION CHAIN)

### LEVEL 1: ON-CALL ENGINEER (YOU)
- Monitors: Pager (SMS), Slack #pilots-incident
- Response time: <5 min for P1, <30 min for P2
- Authority: Restart services, toggle feature flags, manual fallback mode
- Escalation path: If root cause unknown after 15 min → Escalate to CTO

### LEVEL 2: CTO
- Expertise: System architecture, policy engine, integration issues
- Response time: <15 min for P1 (if awoken), <1 hour for P2
- Authority: Code changes, new deployments, incident decision-making
- Escalation: If customer-facing impact >30 min → Escalate to Pilot Manager

### LEVEL 3: PILOT MANAGER
- Expertise: Customer communication, business continuity, media/regulatory response
- Response time: <1 hour for critical incidents
- Authority: Go-live pause decision, apology + compensation if needed
- Escalation: If KARP/regulatory impact → notify board

### LEVEL 4: INCIDENT COMMANDER (ON-CALL ROTATION Q1 2027)
- Role: Post-incident review, prevention planning (future)
- Not yet assigned (you do this manually for Nov-Dec)

---

## P1 (CRITICAL) INCIDENTS — <30 MIN SLA

### INCIDENT TYPE: PII LEAK
**Definition:** Customer email, guest phone, student biometric, or card number appears unmasked in logs

**Detection:**
- Automated PII scanner finds unmasked data (runs daily)
- Customer reports seeing personal info in receipt/email
- Security audit flags data exposure

**IMMEDIATE RESPONSE (0-5 MIN):**
1. Page on-call engineer
2. Page CTO
3. Create #incident-pii Slack channel

**INVESTIGATION (5-15 MIN):**
1. Locate source: Which system? Which decision(s) affected?
2. Scope: How many customers? How many data elements?
3. Timeline: How long was data exposed?
4. Customer visibility: Did customer see this? Did system log it? Did backup contain it?

**REMEDIATION (15-25 MIN):**
- **If exposed to customer:** Delete from customer email, notify customer (template below)
- **If in log only:** Redact logs, restart logging service
- **If in backup:** Mark backup as "contaminated", do not restore from it
- **Root cause:** Which masking rule failed? Load incorrect rule? Edge case?

**VALIDATION (25-30 MIN):**
- Run PII scanner on all logs post-fix (target 0 findings)
- Verify masking rule working correctly on 10 test records
- Check backups are clean
- Document in AP2 ledger + incident log

**POST-INCIDENT (30+ MIN):**
- Write post-mortem: "PII leak: root cause XYZ, fix applied, validation passed"
- Update masking rules (if needed)
- Email CTO + Pilot Manager: "P1 resolved, customer notification [sent/not needed]"
- Log to AP2 ledger as "PII_INCIDENT_DETECTED_AND_CONTAINED"

**CUSTOMER NOTIFICATION TEMPLATE:**
```
Subject: Security Notice - [Company] Incident Response

Dear [Customer Name],

We detected and contained a data security incident on [DATE] at [TIME].
Your [email / phone / biometric reference] may have been briefly exposed in our logs.

What we did:
- Detected exposure immediately (within [X] minutes)
- Isolated affected systems
- Removed personal data from logs
- Notified you within [Y] hours

What you should do:
- Monitor your [email / bank account / school communications] for unusual activity
- Contact us if you notice anything suspicious
- [Add any additional guidance based on data type]

We apologize for this incident. We've implemented additional safeguards [describe changes].

Contact: [your email] or [customer support phone]
```

**ESCALATION DECISION:**
- If customer is public figure or media-connected → Notify Pilot Manager immediately (may need PR response)
- If >100 customers affected → Notify regulatory (ECB for hotel, NANDO for glass, DPA for school)

---

### INCIDENT TYPE: SYSTEM DOWN (ANY PILOT)
**Definition:** Service unavailable >5 minutes (customers can't get approvals, designs reviewed, or access building)

**Detection:**
- Alert fires (service monitoring down, error rate >50%, latency >10s)
- Customer calls: "I can't get access!" / "Design upload failing!"
- Pilot lead reports in standup

**IMMEDIATE RESPONSE (0-2 MIN):**
1. Page on-call engineer
2. Verify: Is it really down? (Check dashboard, try manual access)
3. Create #incident-downtime Slack channel
4. Post: "INCIDENT: [Pilot] system unavailable as of [time], investigating"

**MANUAL FALLBACK (0-5 MIN):**
1. **Hotel:** Switch to manual approval (staff calls credit analyst, analog form)
2. **Glass:** Switch to email-based CAD review (engineers download CAD, review offline, reply via email)
3. **School:** Switch to manual ID checks + manual attendance log (paper forms + Excel)
4. **Goal:** Zero customer denials while system is down

**ROOT CAUSE ANALYSIS (5-15 MIN):**
1. Is it infrastructure (cloud down, network disconnected)?
2. Is it application (code crash, database locked)?
3. Is it data (missing policy file, corrupted AP2 ledger)?
4. Where is the error? Check logs + monitoring dashboard
5. Ask: "Has anything changed in last 2 hours?" (deployment, config change, data ingestion?)

**REMEDIATION (15-25 MIN):**
**Scenario A: Code Deployment Error**
- Rollback: Revert to last known good version
- Verify: Service comes back online + manual tests pass

**Scenario B: Database Issue**
- Check connection pool (exhausted?)
- Restart database service (if safe)
- Verify: Queries responding, data intact

**Scenario C: Configuration Error**
- Reload policy files (if config changed)
- Restart policy engine
- Verify: Decisions executing correctly

**Scenario D: Cascading Failure**
- Identify dependency: Which service is down upstream?
- Restart in dependency order: database → API → business logic → frontend
- Verify: Each layer responding

**VALIDATION (25-30 MIN):**
1. Service health check: Response time <5s, error rate 0%
2. Functional test: Process 5 test decisions, all correct
3. Customer test: Have pilot lead process 1 real decision, confirm it works
4. Resume full operation: Announce system restoration in Slack

**CUSTOMER COMMUNICATION:**
```
#incident-downtime update: [Pilot] service restored at [TIME]
- Downtime duration: [X] minutes
- Root cause: [brief description]
- Customer impact: [N] manual approvals processed
- Fix: [what was done]
- Prevention: [what we'll do to prevent next time]

Thank you for your patience. Service is now fully operational.
```

**POST-INCIDENT:**
- Write post-mortem: "Downtime 15 min, root cause XYZ, fix applied, no data loss"
- Update runbook: Add this scenario for future reference
- Log to AP2 ledger: "DOWNTIME_INCIDENT: duration [X] min, root cause [Y], resolved"
- Email CTO: "P1 resolved, full post-mortem attached"

**ESCALATION DECISION:**
- If downtime >30 min → Notify Pilot Manager (may affect customer SLA)
- If downtime >1 hour → Notify board (operational risk)
- If data loss occurred → Immediate call to legal/compliance

---

### INCIDENT TYPE: FALSE NEGATIVE IN PRODUCTION (GLASS ONLY)
**Definition:** System approved a design that subsequently failed manufacturing safety test (CRITICAL)

**Detection:**
- Manufacturing receives glass from production, fails quality check
- Traceability: Design traceable back to AI approval
- Alert: Quality system flags "AI_APPROVED_BUT_FAILED"

**IMMEDIATE RESPONSE (0-5 MIN):**
1. Page on-call engineer
2. Page CTO
3. Page Safety Lead (external expert)
4. Create #incident-false-negative Slack channel
5. **HALT ALL APPROVALS:** Switch to manual-only mode for glass designs

**INVESTIGATION (5-30 MIN):**
1. **Safety review:** What failed? Which safety check should have caught it?
2. **AI review:** Was design checked? Which safety rules executed? Why did they pass?
3. **Data review:** Was design data corrupted? Was model confidence high?
4. **Pattern:** Is this an isolated incident or systematic failure?

**REMEDIATION (30-60 MIN):**
1. **Add new safety check:** If a safety rule was missing, add it
2. **Adjust threshold:** If a rule threshold was too lenient, tighten it
3. **Retrain if needed:** If model confidence was wrong, recalibrate
4. **Validation:** Re-test on 100 historical designs, verify new rule catches similar failures

**VALIDATION (60-90 MIN):**
1. Manual safety expert review: Can they spot the failure with new rules? Yes.
2. Backtest: Run new rules on 500 historical designs, ensure no similar misses
3. False positive check: Does new rule flag too many safe designs? (goal <5% FP rate)
4. Safety engineer sign-off: "Rule is sound, ready to resume production"

**RESUME PRODUCTION (90-120 MIN):**
1. Deploy new safety rule to production
2. Process 10 test designs, verify new rule executes correctly
3. Resume automatic approvals with new rule in place
4. Announce: "Glass service restored with enhanced safety check XYZ"

**POST-INCIDENT:**
- **CRITICAL:** Write detailed post-mortem: "False negative in design [ID], root cause [specific], new rule added, 500-design backtest passed"
- Log to AP2 ledger as "FALSE_NEGATIVE_INCIDENT: design [ID], root cause, fix applied, validation [passed]"
- Email Safety Lead + CTO + Pilot Manager: Full incident + remediation details
- Notify customer (glass factory): Explain incident, new safeguard, timeline
- Update Glass execution plan: Add this false negative to risk register

**ESCALATION DECISION (CRITICAL):**
- If false negative is systematic (>1 occurrence) → Halt pilot immediately, escalate to board
- If false negative is isolated (1 occurrence, root cause clear, fix validated) → Continue with monitoring
- Either way: Regulatory notification required (NANDO, DPA)

---

## P2 (HIGH) INCIDENTS — <4 HOUR SLA

### INCIDENT TYPE: LATENCY DEGRADATION
**Definition:** p95 latency exceeds threshold (hotel >5s, glass >1s, school >10s) for >30 minutes

**Detection:**
- Monitoring alert: "Latency above threshold"
- Customer reports: "It's taking forever to approve"
- Pilot lead mentions in standup

**RESPONSE (30 MIN TARGET):**
1. Verify: Is latency really above threshold? (Check dashboard)
2. Investigate: What's slow? (API? Database? ML model?)
3. Quick wins: Clear logs, restart slow services, scale if possible
4. If not fixed in 30 min → Escalate to CTO for deeper investigation

**REMEDIATION OPTIONS:**
- Restart service (sometimes helps with memory leaks)
- Clear old logs (if disk full slowing I/O)
- Increase resources (cloud instance scaling)
- Disable non-critical features (e.g., detailed logging)
- Route traffic to backup system (if available)

**VALIDATION:**
- Latency returns to normal (<5s hotel, <1s glass, <5s school)
- Process 20 test decisions, confirm speed
- Monitor for 1 hour to ensure latency stays normal

**POST-INCIDENT:**
- Log: "Latency spike 40 min, root cause [X], fixed by [Y]"
- Trend analysis: Is latency drifting upward over time? (might need proactive scaling)
- Email CTO: "P2 resolved, root cause [X]"

---

### INCIDENT TYPE: FAIRNESS VIOLATION (HOTEL) OR BIOMETRIC DRIFT (SCHOOL)
**Definition:** 
- Hotel: Approval rate disparate impact >1.25x (e.g., 95% approvals for one nationality, 70% for another)
- School: Biometric FAR >1% or FRR >5% (accuracy degrading)

**Detection:**
- Fairness dashboard shows spike (daily check by Pilot Manager)
- Customer complaint: "I was denied unfairly because of my nationality"
- RAGAS evaluation shows accuracy drop

**RESPONSE (4 HOUR TARGET):**
1. Investigate: Which nationality/demographic is affected?
2. Root cause: Is it the policy (too strict for one group)? Or data quality (poor biometric enrollment)?
3. Analyze: How many decisions affected? How far above threshold?
4. Communicate: If <1% of decisions, continue monitoring. If >5%, pause and investigate.

**REMEDIATION:**
- **Policy adjustment:** Loosen threshold slightly if policy too strict
- **Training:** Re-enroll students if biometric quality degraded
- **Investigation:** Is there a demographic with worse data quality? (e.g., dark skin biometric accuracy gap?)
- **Monitoring:** Increase fairness check frequency (daily instead of weekly)

**VALIDATION:**
- Fairness metric returns to <1.25x within 4 hours
- No systematic bias against any demographic
- RAGAS accuracy stable

**POST-INCIDENT:**
- Log: "Fairness violation [X]%, root cause [Y], policy adjusted, [Z] decisions reissued"
- Email CTO + Compliance Officer: Full fairness incident details
- Notify customer: "We detected and corrected a fairness issue [details]"

---

## INCIDENT COMMUNICATION PROTOCOL

### INTERNAL COMMUNICATION
**Immediate (0-5 min):** Create Slack #incident-[type] channel, post one-liner status
```
#incident-pii: PII leak detected in hotel logs, investigating, ~15 min to resolution
```

**Ongoing (5-30 min):** Post updates every 5-10 minutes while investigating
```
#incident-pii: Found unmasked guest email in 3 log entries, isolated, now deploying fix
```

**Resolution (30+ min):** Final status + post-mortem link
```
#incident-pii: RESOLVED. Root cause: masking rule not applied to escalation queue. 
Fix deployed 02:30 UTC. Validation passed. Post-mortem: [link]
All 3 customers notified individually.
```

### EXTERNAL COMMUNICATION (IF CUSTOMER-FACING)

**IF <15 MINUTES DOWNTIME:**
No communication needed (SLA allows small blips)

**IF 15-60 MINUTES DOWNTIME:**
Send email to pilot contact (CTO at customer) within 2 hours:
```
Subject: [System] Incident Report - [Time] Downtime

We experienced a [duration] service outage starting [time UTC].
Root cause: [brief non-technical description]
Impact: [approvals delayed / designs not reviewed / access denied]
Resolution: [what we did]
Status: Fully operational as of [time]

We apologize for the disruption. [If compensation needed: offer credit/refund]
```

**IF >60 MINUTES DOWNTIME OR PII LEAK:**
Call customer CTO immediately + follow up with written incident report

---

## STRESS TEST PROCEDURES (WEEK 8 ONLY)

### PLANNED STRESS TESTS (Not incidents, log separately)
These are deliberate tests to prove system resilience. Don't page on-call for these.

**Hotel: Holiday Surge Simulation**
- Increase booking volume 3x normal (250 approvals in single day)
- Monitor: Latency doesn't exceed p95 <5s, fairness maintained
- Manual fallback if queue > 20 pending

**Glass: Year-End Volume Test**
- Process 50+ designs in single week (peak period)
- Monitor: Latency <1s maintained, false negative rate = 0%
- Document cost per design ($0.85 target)

**School: 48-Hour Network Outage + Durability Test** (CRITICAL)
- Disconnect internet for 48 consecutive hours
- Monitor: System continues on local cache, 800+ access attempts processed
- After reconnection: All 800 events sync to cloud within 5 minutes
- Verify: Zero data loss, AP2 ledger complete

**Stress Test Protocol:**
1. **Announce:** Post in #pilots-incident "Starting [test] at [time], expected duration [X] hours"
2. **Monitor:** Watch metrics in real-time (latency, error rate, system health)
3. **Document:** Screenshot key metrics before/during/after
4. **Validate:** After test, verify system returned to normal
5. **Report:** Post results in Slack + log to AP2 ledger as "PLANNED_STRESS_TEST: [results]"

---

## ON-CALL ENGINEER CHECKLIST

### BEFORE GOING ON-CALL
- [ ] Have SMS pager working? Test it.
- [ ] Have Slack open on phone + desktop?
- [ ] Have access to all 3 pilot dashboards (links)?
- [ ] Have CTO + Pilot Manager phone numbers?
- [ ] Have list of pilot customer contacts (for P1 calls)?
- [ ] Have incident response playbook downloaded (this document)?
- [ ] Have database access + code repo access?

### DAILY STANDUP (9:00 AM CET, YOU LEAD)
- [ ] "Current status: All 3 pilots healthy? Any overnight incidents? [Pilot leads respond]"
- [ ] "Today's focus: [scheduled stress tests / important milestones]"
- [ ] "On-call coverage: I'm on until [time tomorrow]"

### DAILY END-OF-SHIFT (6:00 PM CET, YOU REPORT)
- [ ] "P1 incidents today: [count, brief summary]"
- [ ] "P2 incidents today: [count, brief summary]"
- [ ] "System health: All pilots green? Any concerns for next shift?"
- [ ] "Handoff notes: [anything successor should watch for]"

### OVERNIGHT PROTOCOL (6:00 PM - 9:00 AM CET)
- [ ] You're asleep but reachable by SMS pager
- [ ] P1 alert → You get SMS, wake up, respond <5 min
- [ ] P2 alert → You get SMS, respond <30 min (or next morning if <4h until resolution)
- [ ] If you need help, call CTO first, then Pilot Manager

### END-OF-MONTH HANDOFF (TO SERIES A HIRE IF AVAILABLE)
- [ ] Meet with new on-call engineer
- [ ] Run through 3 biggest incidents from past month
- [ ] Show them dashboards, alert channels, escalation numbers
- [ ] Have them shadow for 1 week before taking solo on-call

---

## CRITICAL PHONE NUMBERS & CONTACTS

```
Pilot Manager: [Your email] / [Your phone] (primary contact)
CTO: [CTO name] / [CTO phone] (system/technical issues)
Hotel Pilot Lead: [Name] / [Phone] (hotel incidents)
Glass Pilot Lead: [Name] / [Phone] (glass incidents)
School Pilot Lead: [Name] / [Phone] (school incidents)

Hotel Customer CTO: [Hotel chain name] [CTO] / [Phone] (escalation)
Glass Customer CTO: [Manufacturer name] [CTO] / [Phone] (escalation)
School Customer Admin: [School name] [Principal/IT Director] / [Phone] (escalation)

Regulatory Escalation:
  - ECB (Hotel): [Contact] / [Email] (fairness violations)
  - NANDO (Glass): [Contact] / [Email] (false negative in production)
  - DPA (School): [Contact] / [Email] (GDPR violations)

Emergency Services (if physical safety):
  - Glass Factory Safety: [Safety Manager phone] (design failure in production)
  - School Security: [Security phone] (biometric tampering)
```

---

## SUCCESS METRICS FOR SUPPORT

By Dec 31, 2026:
- ✅ P1 incidents: <3 total (target <1% of decisions)
- ✅ P2 incidents: <10 total (target <5% of decisions)
- ✅ P1 resolution SLA: 100% <30 min (all resolved within target)
- ✅ P2 resolution SLA: 95% <4 hours (acceptable, 1-2 may exceed)
- ✅ Customer satisfaction: 0 complaints about on-call response
- ✅ Zero cascading failures (1 pilot down doesn't affect others)
- ✅ Zero duplicate incidents (each class of incident happens <2 times)

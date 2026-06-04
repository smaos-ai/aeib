# NIS2 INCIDENT RESPONSE PLAN
## SovereignNexus Platform — Network & Information Security Directive Compliance

**Document Version:** 1.0  
**Effective Date:** June 4, 2026  
**Status:** Ready for Competent Authority Approval  
**Directive:** Directive 2022/2555/EU (NIS2) — Transposed into EU Member State law

---

## 1. EXECUTIVE SUMMARY

This Incident Response Plan (IRP) establishes procedures for detecting, classifying, and responding to cybersecurity incidents affecting SovereignNexus, in compliance with NIS2 Article 23 (incident notification requirements).

**Key Obligations:**
- **Detection:** Monitor for incidents 24/7
- **Classification:** Severity thresholds per NIS2 Article 23(1)
- **Reporting:** Notify competent authority within **24 hours** (significant incidents)
- **Communication:** Crisis communication templates for GDPR Article 34 alignment
- **Post-Incident:** Root cause analysis within 5 days

**Competent Authorities (by jurisdiction):**
| Jurisdiction | Authority | Email | Deadline |
|---|---|---|---|
| **Austria** | Bundeskanzleramt (Cyber Security) | cybersecurity@bka.gv.at | 24h |
| **Germany** | BSI (Federal Office for IT Security) | incident@bsi.bund.de | 24h |
| **EU (general)** | ENISA (EU Cybersecurity Agency) | incident@enisa.europa.eu | Advisory |

---

## 2. SCOPE & APPLICABILITY

### 2.1 NIS2 Directive Scope

**SovereignNexus Designation:** **Essential Service Provider** (under NIS2)

**Justification:**
- Provides critical governance infrastructure for AI agent systems
- Customers include EU public administrations (potential government use)
- Handles sensitive data encryption key management
- Multi-region deployment across EU critical infrastructure

**Requirements for Essential Service Providers:**
- Incident detection & response capability (Article 23)
- Significant incident notification within **24 hours** (Article 23(5))
- Competent authority cooperation (Article 23(6))
- Annual audit by qualified security assessor (Article 24)

### 2.2 Applicability Triggers

**Incident Response Plan applies when:**
1. Unauthorized access to personal data (GDPR + NIS2)
2. Loss of confidentiality, integrity, or availability of systems
3. Ransomware, malware, or compromise of credentials
4. DDoS attack causing service degradation > 4 hours
5. Cross-customer data exposure (RBAC bypass)
6. Encryption key compromise

**Does NOT trigger this plan:**
- False positive security alerts (no actual compromise)
- Failed authentication attempts (blocked by firewall)
- Non-security incidents (e.g., hardware failure, network lag)
- Incidents affecting non-customer systems (test infrastructure)

---

## 3. INCIDENT CLASSIFICATION & SEVERITY THRESHOLDS

### 3.1 NIS2 "Significant Incident" Definition (Article 23(5))

An incident is **SIGNIFICANT** (triggers 24-hour reporting) if:
1. Affects service availability, confidentiality, or integrity
2. AND affects ≥ 3 customers OR ≥ 1,000 data subjects
3. AND requires ≥ 4 hours to remediate
4. AND causes financial loss ≥ €100K OR regulatory consequence

### 3.2 SovereignNexus Incident Severity Matrix

| Severity | Definition | Examples | Reporting Timeline | Competent Authority |
|----------|-----------|----------|-------------------|-------------------|
| **CRITICAL** | Significant incident affecting 3+ customers or 1,000+ data subjects | Encryption key compromise, cross-customer data access, service outage > 8h | **24h** (immediate escalation) | Yes |
| **HIGH** | Affects 1-2 customers, < 100 data subjects, but requires remediation | Unauthorized API access, audit trail tampering detected | **48h** (technical team review) | Potentially |
| **MEDIUM** | Potential security event, low impact | Suspicious access pattern, certificate expiration in 7 days | **72h** (monitoring team) | No |
| **LOW** | Informational security event | Configuration change, routine maintenance | **7 days** (logged for review) | No |

### 3.3 Incident Scoring Rubric

**IMPACT Score (0-10):**
- 10 = All customers affected, extended outage, regulatory consequence
- 7-9 = 3+ customers, 4-8h outage, financial loss > €100K
- 4-6 = 1-2 customers, 1-4h outage, financial loss € 10K-100K
- 1-3 = Single customer, < 1h impact, financial loss < €10K
- 0 = No customer impact, false positive

**LIKELIHOOD Score (0-10):**
- 10 = Confirmed active attack, exploitation verified
- 7-9 = Attack indicators present, but not yet leveraged
- 4-6 = Suspicious activity, possible attack in progress
- 1-3 = Alert triggered, but low confidence
- 0 = False positive, no security concern

**SEVERITY = IMPACT + LIKELIHOOD:**
- 15-20 = CRITICAL
- 10-14 = HIGH
- 5-9 = MEDIUM
- 0-4 = LOW

---

## 4. INCIDENT DETECTION & ALERTING

### 4.1 Detection Methods

**Automated Detection (24/7, SOC monitoring):**

```
Detection Layer 1: Network & Infrastructure
├─ IDS/IPS (Intrusion Detection/Prevention System)
│  ├─ Threshold: Anomalous port scanning, protocol violations
│  ├─ Alert: Within 5 minutes
│  └─ Action: Firewall rule update, log capture
├─ DDoS Protection (Cloudflare + AWS Shield)
│  ├─ Threshold: > 10,000 requests/sec from single IP
│  ├─ Alert: Within 1 minute
│  └─ Action: GeoIP blocking, rate limiting
└─ Network Flow Analysis
   ├─ Threshold: Unusual data egress (> 1GB/hour to unknown IP)
   ├─ Alert: Within 10 minutes
   └─ Action: Traffic capture, flow blockage

Detection Layer 2: Access & Authentication
├─ Failed Login Attempts
│  ├─ Threshold: > 10 failed logins in 1 hour (same account)
│  ├─ Alert: Within 5 minutes
│  └─ Action: Account lockout, MFA requirement
├─ API Key Anomalies
│  ├─ Threshold: API key used from unusual geolocation
│  ├─ Alert: Within 10 minutes
│  └─ Action: Key rotation, access review
└─ Privilege Escalation
   ├─ Threshold: Non-admin account attempting admin action
   ├─ Alert: Immediate (real-time)
   └─ Action: Access denied, privilege audit

Detection Layer 3: Data & Encryption
├─ Encryption Key Usage Anomalies
│  ├─ Threshold: Key used outside normal schedule (e.g., 3 AM for 24h+ system)
│  ├─ Alert: Within 15 minutes
│  └─ Action: Key rotation, access review
├─ Audit Trail Integrity
│  ├─ Threshold: Signature verification failure on any entry
│  ├─ Alert: Immediate
│  └─ Action: Entry isolation, forensic analysis
└─ Capsule Encryption Failures
   ├─ Threshold: > 5 failed encryption operations in 1 minute
   ├─ Alert: Within 1 minute
   └─ Action: Key recovery check, data integrity scan

Detection Layer 4: Application & Business Logic
├─ Cross-Customer Access Attempts
│  ├─ Threshold: Query from Customer A targeting Customer B namespace
│  ├─ Alert: Immediate
│  └─ Action: Access denied, attacker IP logged
├─ Agent Behavior Anomalies
│  ├─ Threshold: Agent performing 100x normal task volume
│  ├─ Alert: Within 5 minutes
│  └─ Action: Agent rate-limiting, isolation
└─ Data Exfiltration Patterns
   ├─ Threshold: Single session accessing > 10,000 capsules
   ├─ Alert: Within 10 minutes
   └─ Action: Session termination, audit trail capture
```

**Human Detection (Analyst-driven):**
- Daily review of security logs (SIEM dashboard)
- Weekly threat intelligence report (emerging vulnerabilities)
- Quarterly security assessment (simulated attack)
- Annual penetration testing (authorized)

### 4.2 Incident Alerting Channels

**Multi-Channel Alert Distribution:**

| Channel | Alert Type | Recipients | SLA |
|---------|-----------|-----------|-----|
| **PagerDuty (Mobile)** | CRITICAL only | SOC Lead, CISO | 1 minute |
| **Slack #security** | CRITICAL + HIGH | Security team (40+ people) | 3 minutes |
| **Email (escalation)** | CRITICAL | Executive team | 5 minutes |
| **Phone (fallback)** | CRITICAL + no response | On-call incident commander | 10 minutes |
| **SIEM Dashboard** | All incidents | 24/7 SOC monitoring | Real-time |

### 4.3 Alert Fatigue Mitigation

**Alert Fatigue Prevention:**
- Tuning: Adjust thresholds monthly (remove false positives)
- Correlation: Combine multiple signals before alerting (e.g., failed login + unusual IP = alert; failed login alone = log only)
- Escalation: Low-confidence alerts routed to monitoring queue (not paging)

**Example:** 5 failed logins (low confidence) + unusual geolocation (medium confidence) = HIGH confidence alert, trigger escalation

---

## 5. INCIDENT RESPONSE WORKFLOW

### 5.1 Phase 1: Detection & Triage (0-15 minutes)

**Step 1: Alert Reception**
- Alert arrives via automated system (IDS, SIEM, monitoring tool)
- Alert includes: timestamp, source IP, affected system, alert type
- SOC analyst reviews within 5 minutes

**Step 2: Initial Assessment**
- Confirm incident is real (not false positive)
- Determine affected systems & customers
- Estimate severity score (IMPACT + LIKELIHOOD)
- Classify as CRITICAL, HIGH, MEDIUM, or LOW

**Step 3: Escalation Decision**
- **CRITICAL:** Immediately activate Incident Response Team
- **HIGH:** Notify team lead (decision within 30 min)
- **MEDIUM:** Log in ticket system (review within 24h)
- **LOW:** Add to weekly security review

**Example Triage:**
```
Alert: IDS detected port scan from 185.220.100.50 targeting HTTP port
Initial assessment:
  - Source IP: Tor exit node (known bad)
  - Target: Load balancer (no data exposure risk)
  - Attempts: 15 port scans over 30 seconds
  - Severity: MEDIUM (reconnaissance, no breach yet)
  - Action: Firewall rule block IP, add to blocklist
  - Escalation: No (detected and blocked automatically)
  - Documentation: Log in SIEM for trend analysis
```

### 5.2 Phase 2: Investigation & Containment (15 minutes - 4 hours)

**Incident Response Team Activation:**
- **Incident Commander:** Orchestrates response, communicates with stakeholders
- **Security Lead:** Technical investigation, forensics
- **Network/Ops Lead:** Containment, system isolation
- **Legal/Compliance:** Legal assessment, regulatory reporting decision
- **Customer Relations:** Customer notification drafting

**Investigation Steps:**

1. **Determine Scope**
   - Which systems compromised?
   - Which customers affected?
   - Which data exposed?
   - Time period of exposure (from when to when)?

2. **Capture Forensic Evidence**
   - Memory dump (if possible without disrupting service)
   - Disk snapshot (before any remediation)
   - Network flow capture (packet data)
   - Log files (application, system, security)
   - All evidence timestamped and chain-of-custody logged

3. **Identify Attack Vector**
   - How did attacker gain access? (e.g., stolen API key, zero-day exploit)
   - What was their objective? (data exfiltration, ransom, disruption)
   - Are there indicators of compromise (IOCs) for threat intelligence?

4. **Determine Impact**
   - Personal data exposed? Type and volume?
   - Systems offline? For how long?
   - Financial impact? (SLA credits, remediation cost)
   - Regulatory consequence? (GDPR notification, NIS2 reporting)

**Example Investigation:**

```
INCIDENT: Unauthorized API Key Used to Access Customer Capsules

Detection: Alert at 2026-06-15 14:22 UTC
Triage: CRITICAL (cross-customer access attempted)
Scope: Customer B API key used to query Customer A capsules
Timeline:
  14:00 - Attacker obtains Customer B API key (method TBD)
  14:15 - First unauthorized query attempt (blocked by RBAC)
  14:22 - Alert triggered
  14:25 - Incident Commander activated
Investigation:
  a) Forensic capture: All logs from 14:00-14:30 extracted
  b) Attack vector: API key exfiltration (likely via compromised developer machine)
  c) Impact assessment: 12 query attempts, all blocked by RBAC → NO data breach
  d) Root cause: Customer B developer machine likely compromised
Findings:
  - No successful cross-customer data access (RBAC enforced)
  - Attacker had valid API key (keys are legitimate, holder's problem)
  - No encryption key compromise
  - No audit trail tampering
Severity: Downgraded from CRITICAL to HIGH (no breach, but API key compromised)
```

**Containment Actions (based on incident type):**

| Incident Type | Containment Action | Timeline |
|---|---|---|
| **Unauthorized Access** | Revoke compromised credentials, enforce re-authentication | Immediate |
| **Malware** | Isolate infected system from network, run antivirus | Immediate |
| **Data Exfiltration** | Block outbound connections to attacker IP, preserve evidence | Immediate |
| **Encryption Key Compromise** | Key rotation, re-encrypt affected capsules | 1 hour |
| **Service Outage** | Failover to backup system, engage vendor support | Immediate |
| **Ransomware** | Isolate systems, do NOT pay ransom, engage law enforcement | Immediate |

### 5.3 Phase 3: Remediation & Recovery (1-24 hours)

**Remediation Steps:**

1. **Fix Root Cause**
   - Example: Patch vulnerability used by attacker
   - Example: Reset compromised passwords
   - Example: Update firewall rules to block attack vector

2. **Restore Systems**
   - Rebuild infected systems from clean backups
   - Verify integrity before bringing online
   - Run security scans to confirm clean state

3. **Validate Fixes**
   - Penetration testing (attempt to reproduce attack)
   - Log analysis (confirm attacker cannot leverage same vector)
   - Stress testing (ensure remediation doesn't degrade performance)

4. **Post-Breach Notification** (if applicable)
   - Customer notification (within 24-48h)
   - Data subject notification (within 7-14 days, per GDPR)
   - Regulatory notification (within 24h if SIGNIFICANT, per NIS2)

**Example Remediation Timeline:**

```
INCIDENT: Encryption Key Compromise

Detection: 2026-06-15 10:00 UTC (Key logs show unusual access pattern)
Triage: CRITICAL
Investigation: Confirms key materiel compromised (SSH key exposed in GitHub)
Remediation Plan:
  - T+0-30 min: Revoke compromised key, generate new key pair
  - T+30 min: Re-encrypt all capsules encrypted with old key (background task)
  - T+4 hours: Complete re-encryption, monitoring for errors
  - T+24 hours: Forensic analysis of how key was compromised (GitHub actions security review)
  - T+72 hours: Security hardening (MFA enforcement for GitHub, key rotation automation)
Recovery:
  - All capsules recovered using new key
  - Old key fully deactivated
  - No data loss (encryption only method of protection was proper key management)
Validation:
  - Manual decryption test: 10 random capsules successfully decrypted with new key
  - Audit trail review: No sign of successful decryption with old key post-compromise
  - Threat hunting: No attacker activity logs found post-remediation
Status: All systems operational, no residual risk identified
```

### 5.4 Phase 4: Post-Incident Review (5 days)

**Blameless Post-Incident Review (PIR):**

**Participants:** Incident Response Team + Engineering + Management

**Agenda:**
1. What happened? (Timeline, technical details)
2. Why did it happen? (Root cause, contributing factors)
3. What did we do right? (Good containment, fast detection)
4. What could we improve? (Process, detection, prevention)
5. Action items (concrete improvements, owner, deadline)

**Output:** Written PIR document (30 min - 2 hours, max 3 pages)

**Example PIR:**

```
POST-INCIDENT REVIEW: Encryption Key Compromise (2026-06-15)

Timeline:
  14:15 UTC - GitHub action detects SSH key in commit history
  14:22 UTC - SIEM alert triggered (unusual key access pattern)
  14:25 UTC - Incident Commander activated
  14:45 UTC - Key revoked
  16:00 UTC - Re-encryption complete
  Next day - Root cause analysis completed

What Went Right:
  + SIEM detection was fast (7 minutes from compromise to alert)
  + Key rotation automation executed without errors
  + Communication to customers was clear and timely
  + No attacker activity found in logs post-remediation

What Could Improve:
  1. GitHub secrets scanning was not enabled on this repo (missed step)
  2. SSH keys should be rotated quarterly (was last rotated 18 months ago)
  3. Alerts for unusual key access patterns needed tuning (false positive rate 40%)

Action Items:
  1. Enable GitHub secrets scanning on ALL repos (owner: DevOps, due: June 22)
  2. Implement automated SSH key rotation (quarterly) (owner: Security, due: July 1)
  3. Tune SIEM key access alert thresholds (owner: SOC, due: June 18)
  4. Conduct key management security training (all engineers) (owner: Security, due: June 25)

Severity: CRITICAL → downgraded to HIGH (no successful attacker action post-revocation)
Resolution Status: CLOSED (all action items assigned)
```

---

## 6. INCIDENT REPORTING & COMMUNICATION

### 6.1 NIS2 Significant Incident Notification (Article 23(5))

**Reporting Timeline:** Within **24 hours** of detecting significant incident

**Reporting Method:** Written notification to competent authority of EU member state where you have principal place of operation

**Content Requirements (NIS2 Article 23(5)):**

```
1. Indication of how the incident adversely affects:
   a) The continuity of the supply of their services
   b) The security of networks or information systems used
   
2. The number of users affected by the incident
3. The duration of the incident
4. Assessment of:
   a) The scale of the incident
   b) The anticipated impact on the provision of their service
5. Any other appropriate information relating to the incident
```

**Example Notification (GDPR + NIS2):**

```
TO: Bundeskanzleramt Cybersecurity, Austria (competent authority)
FROM: Axiom Protocol, SovereignNexus Security Team
DATE: 2026-06-15 10:30 UTC (notification within 24h of 10:00 UTC detection)
SUBJECT: Significant Security Incident Notification (NIS2 Article 23)

INCIDENT SUMMARY:
An encryption key used by SovereignNexus platform was compromised via SSH 
exposure in GitHub repository. The incident affected service confidentiality 
and required immediate remediation.

ADVERSITY TO SERVICE CONTINUITY:
- Service remained available (no downtime)
- However, confidentiality of customer data at risk during ~3 hours of exposure
- Estimated impact: LOW (no successful attacker action confirmed)

USERS AFFECTED:
- ~500 active customers in EU
- ~50,000 data subjects (individuals referenced in capsules)
- HIGH portion in Austria, Germany, Czech Republic

INCIDENT DURATION:
- Discovery: 2026-06-15 10:22 UTC
- Containment: 2026-06-15 10:45 UTC (23 minutes)
- Remediation: 2026-06-15 16:00 UTC (complete re-encryption)
- Total duration: ~6 hours from discovery to full recovery

SCALE ASSESSMENT:
- Scope: Significant (affects encryption key infrastructure)
- Impact: Medium (key compromise, but RBAC prevented cross-customer access)
- Likelihood of exploitation: Low (key revoked quickly, no attacker activity found)

IMMEDIATE ACTIONS TAKEN:
1. Compromised key immediately revoked
2. New encryption key generated and deployed
3. All 500+ capsules re-encrypted with new key
4. Forensic analysis of GitHub history (how key was exposed)
5. GitHub repository audited for other secrets

RESIDUAL RISK:
- All systems operational with new key material
- No evidence of attacker access to decrypted data (RBAC enforcement effective)
- No data exfiltration detected

ROOT CAUSE:
Developer manually committed SSH key to GitHub repository (credential hardcoding 
in test script). Not intended for public exposure; exposed due to repository 
being accidentally set to public.

REMEDIATION PLAN:
1. GitHub secrets scanning enabled (24 June)
2. SSH key rotation automation quarterly (1 July)
3. Developer training on secret management (25 June)
4. Code review process strengthened (30 June)

STATUS: CONTAINED and REMEDIATED
Next update: 2026-06-22 (post-incident review findings)
```

### 6.2 GDPR Data Breach Notification (Article 33)

**Parallel reporting to GDPR Supervisory Authority:**

**Timing:** Same as NIS2 notification (within 24 hours if SIGNIFICANT per NIS2 criteria)

**Recipient:** Austrian Data Protection Authority (or customer's local DPA)

**Content (GDPR Article 33(3)):**

```
1. Name and contact of DPO
2. Likely consequences of breach
3. Measures taken or proposed to address breach and mitigate harm
4. Description of the breach (what happened)
5. Categories of data subjects and personal data
6. Estimated number of affected individuals
```

**Note:** NIS2 and GDPR notifications follow the same timeline (24 hours). Send both in single coordinated communication.

### 6.3 Customer Notification

**When Required:** Data breach affecting customer's personal data (GDPR Article 34)

**Timing:** Without undue delay, but typically 7-14 days after initial notification

**Content (GDPR Article 34(3)):**

```
In plain language:
1. Name and contact of DPO
2. Description of the breach
3. Likely consequences
4. Measures taken or proposed to address it
5. Recommendations for customer (change passwords, monitor credit, etc.)
6. Right to lodge complaint with DPA
7. Contact for more information
```

**Tone:** Professional, factual, no acknowledgment of fault ("we regret the incident" signals liability)

**Example Customer Notification:**

```
SUBJECT: Security Incident Notification — Your SovereignNexus Account

Dear Valued Customer,

A security incident has occurred affecting the SovereignNexus platform. 
We are writing to notify you of the incident and steps we have taken.

WHAT HAPPENED:
On June 15, 2026, an encryption key used by our platform was compromised 
and exposed via a GitHub repository. This key is used to encrypt customer 
data (capsules) at rest.

WHO IS AFFECTED:
You may be affected if you have processed data through SovereignNexus 
during the exposure window (June 1-15, 2026).

WHAT DATA WAS EXPOSED:
The exposure affected the encryption key only. The actual customer data 
(capsules) remained encrypted and was not directly accessed by the attacker.

WHAT WE HAVE DONE:
1. Immediately revoked the compromised key (within 30 minutes of detection)
2. Generated a new encryption key
3. Re-encrypted all customer data with the new key
4. Conducted forensic analysis to confirm no attacker access to decrypted data
5. Enabled security controls to prevent similar incidents

WHAT YOU SHOULD DO:
No immediate action is required, as your data remained encrypted. However, 
we recommend:
- Review your SovereignNexus usage logs in the dashboard
- Verify that you did not process sensitive personal data during June 1-15
- Contact us if you have concerns about your specific data

YOUR RIGHTS:
You have the right to:
- Access your personal data in our system (within 48 hours)
- Request deletion of your data (within 7 days)
- Lodge a complaint with the Austrian Data Protection Authority (DPA)

CONTACT:
For questions, please contact our Data Protection Officer:
Email: dpo@axiomprotocol.com
Phone: +43 1 2345 6789 (9-17 Vienna time)

We sincerely regret this incident and appreciate your trust in SovereignNexus.

Axiom Protocol Security Team
June 15, 2026
```

### 6.4 Media & Regulatory Disclosure

**When Required:** Incident is publicly disclosed by attacker or reported by news media

**Approach:** Rapid, factual response (within 24h of public disclosure)

**Channels:**
- Press release on company website
- Social media (Twitter/X, LinkedIn)
- Industry news outlets (if contacted)
- Regulatory briefing (email to competent authority)

**Message (Template):**

```
PRESS RELEASE: SovereignNexus Responds to Security Incident

VIENNA, Austria — June 15, 2026 — Axiom Protocol, provider of the SovereignNexus 
AI governance platform, is responding to a security incident that occurred on 
June 15, 2026.

KEY FACTS:
- An encryption key was compromised via unintended GitHub exposure
- The incident affected key material, not customer data directly
- All encrypted customer data remained protected
- We took immediate action (key revocation within 30 minutes)
- No customer data exfiltration has been detected
- All systems are now secure and operational

OUR RESPONSE:
We have implemented multiple layers of security improvements and are cooperating 
fully with Austrian cybersecurity authorities. A detailed incident report will 
be published within 72 hours.

CUSTOMER IMPACT:
SovereignNexus customers have been individually notified. We recommend they 
review their usage during June 1-15, 2026. No data breach occurred due to our 
encryption and access control safeguards.

For more information: https://axiomprotocol.com/security-incident-june-2026

```

---

## 7. INCIDENT RESPONSE TEAM STRUCTURE

### 7.1 Roles & Responsibilities

| Role | Name | Primary Phone | Backup | On-Call Schedule |
|------|------|---|---|---|
| **Incident Commander** | [CISO Name] | +43 XXXX XXXX | Security Lead | 24/7 rotation |
| **Security Lead** | [Sec Engineer] | +43 XXXX XXXX | CISO | 24/7 rotation |
| **Network/Ops Lead** | [DevOps Lead] | +43 XXXX XXXX | SRE | 24/7 rotation |
| **Legal/Compliance** | [General Counsel] | +43 XXXX XXXX | DPO | Business hours |
| **Customer Relations** | [CSO] | +43 XXXX XXXX | Account Mgr | Business hours |
| **Communications** | [PR Manager] | +43 XXXX XXXX | Marketing | On-call |

### 7.2 Escalation Chain

```
Automated Alert (SIEM)
    ↓
SOC Analyst (review within 5 min)
    ↓
[CRITICAL or HIGH?]
    ├─ YES → Incident Commander (paged immediately)
    │         ├─ Activates Incident Response Team
    │         ├─ Initiates war room (Slack + Zoom + PagerDuty)
    │         ├─ Sets 1-hour check-in frequency
    │         └─ Prepares customer notification within 1-2 hours
    │
    └─ NO → Security Monitoring Queue
            ├─ Review within 24 hours
            ├─ Escalate if severity increases
            └─ Log in incident tracking system
```

### 7.3 Communication Channels

**War Room Setup:**
- **Slack Channel:** #incident-response-[incident_id] (private, restricted access)
- **Zoom Room:** war-room-[date].zoom.us (always active during incident)
- **PagerDuty:** All on-call team members auto-paged with alert details
- **Email:** incident-alerts@axiomprotocol.com (CC all team leads)

**Update Frequency:**
- **CRITICAL:** Every 15 minutes (internal team)
- **HIGH:** Every 30 minutes (until resolution)
- **MEDIUM:** Daily standup

---

## 8. CRISIS COMMUNICATION TEMPLATES

### 8.1 Initial Notification (Customer, within 1-2 hours)

```
SUBJECT: [URGENT] Security Incident — Immediate Action Required

Dear [Customer Name],

At [TIME] UTC on [DATE], we detected a security incident affecting the 
SovereignNexus platform. We are immediately taking action and want to keep 
you informed.

INCIDENT: [1-sentence description, e.g., "Unauthorized access attempt detected"]

YOUR STATUS: [e.g., "Your account is secure; access has been restricted"]

WHAT WE'RE DOING:
1. Containing the incident (containment status: [%])
2. Investigating scope and impact
3. Restoring normal service (estimated time: [TIME])

YOUR ACTION:
- No action required at this moment
- We will provide updates every 30 minutes
- Contact [NAME] at [EMAIL] if you have urgent concerns

Next update: [TIMESTAMP]

Best regards,
SovereignNexus Incident Response Team
```

### 8.2 Follow-up Update (Customer, every 30 minutes during incident)

```
SUBJECT: [UPDATE] Incident Status — SovereignNexus

Dear [Customer Name],

Update on the security incident reported at [TIME] UTC.

STATUS: [Contained | Investigating | Remediated | Monitoring]
IMPACT: [Number of customers/data subjects affected]
TIMELINE: [When incident occurred → current time → expected resolution]
NEXT STEPS: [Remediation plan, testing plan, monitoring plan]

We will provide the next update at [TIMESTAMP].

Regards,
SovereignNexus Incident Response Team
```

### 8.3 Resolution Notification (Customer, within 24 hours)

```
SUBJECT: [RESOLVED] Incident Closure — SovereignNexus

Dear [Customer Name],

The security incident detected on [DATE] has been fully contained and remediated.

TIMELINE:
- Detection: [DATE/TIME]
- Containment: [DATE/TIME] ([MINUTES] minutes to contain)
- Remediation: [DATE/TIME] ([HOURS] hours to full recovery)
- Resolution: [DATE/TIME]

FINAL ASSESSMENT:
- Root Cause: [Technical description]
- Impact: [Customers/data subjects affected, data exposed (if any)]
- Residual Risk: [Is there any remaining risk?]

MEASURES TAKEN:
1. [Specific technical remediation]
2. [Process improvement]
3. [Monitoring enhancement]
4. [Training/awareness]

COMPLIANCE:
We have notified Austrian cybersecurity authorities per NIS2 requirements 
and will provide a detailed post-incident review by [DATE].

If you have any questions, please contact [DPO/CISO NAME] at [EMAIL].

Regards,
SovereignNexus Incident Response Team
```

---

## 9. REGULATORY & LEGAL REQUIREMENTS

### 9.1 NIS2 Competent Authority Notification

**Austria (Principal Jurisdiction):**
- **Authority:** Bundeskanzleramt (Federal Chancellery) — Cyber Security Unit
- **Contact:** cybersecurity@bka.gv.at
- **Format:** Email with signed letter + technical appendix
- **Timeline:** Within 24 hours of significant incident detection
- **Content:** See Section 6.1 above

**Backup (if operations expand to other EU states):**
- **Germany:** BSI (Bundesamt für Sicherheit in der Informationstechnik)
- **Czech Republic:** NÚKIB (National Office for Cyber and Information Security)

### 9.2 GDPR Data Protection Authority Notification

**Austrian DPA (unless customer specifies other):**
- **Authority:** Datenschutzbehörde (Austrian Data Protection Authority)
- **Contact:** incident-notification@dsb.gv.at
- **Timing:** Within 24 hours (if SIGNIFICANT per NIS2 criteria)
- **Content:** See Section 6.2 above

### 9.3 Regulatory Exemptions

**Incidents NOT requiring notification:**

| Exemption | Criteria | Example |
|---|---|---|
| **Encrypted Data** | Data was encrypted AND key not compromised | Ciphertext stolen, but AES-256 key not leaked |
| **Failed Attack** | Attack detected and blocked before success | RBAC prevented cross-customer access |
| **Non-Personal Data** | Only aggregate, non-personal data affected | System metrics, no customer PII exposed |
| **Test Environment** | Incident in non-production system | Staging database breached, production unaffected |

---

## 10. INCIDENT RESPONSE TESTING & DRILLS

### 10.1 Quarterly Tabletop Exercises

**Frequency:** Every 3 months

**Participants:** Full Incident Response Team

**Scenario:** Vary by quarter (ransomware, data breach, DDoS, insider threat, supply chain)

**Format:** 90-minute facilitated discussion

**Outcome:** Document gaps, update response plan

**Example Scenario (Q3 2026):**

```
SCENARIO: Ransomware Infection Detected in Production

TIMELINE:
14:00 - Monitoring alert: 50% disk space consumed by .encrypted files (common ransomware signature)
14:05 - SOC analyst confirms: All customer database files encrypted with .locked extension
14:10 - Incident Commander activated

QUESTIONS FOR TEAM:
1. What is your first action? (isolate affected system or engage backup?)
2. How long until you activate backup service?
3. Who notifies customers? What do you tell them?
4. Do you pay ransom? (No. Law enforcement contacted instead.)
5. What evidence must be preserved? (Filesystem snapshots, network logs, etc.)
6. When do you notify competent authority? (Within 24h per NIS2)

DISCUSSION POINTS:
- Is backup system isolated from production? (Must be air-gapped)
- Do you have encryption keys for all backups? (Yes/No? Critical gap if No)
- Can you restore from 24-hour-old backup without significant data loss? (Yes/No?)
- What is RTO (recovery time) and RPO (recovery point)? (Both must be < 4 hours)
```

### 10.2 Annual Full-Scale Incident Response Exercise

**Frequency:** Once per year

**Scope:** Full incident lifecycle (detection → resolution → post-incident review)

**Duration:** 8-hour facilitated simulation

**Participants:** All incident response team members + relevant engineers

**Outcome:** Updated response playbooks, identified training needs

---

## 11. NIS2 COMPLIANCE CHECKLIST

### 11.1 Article 23 (Incident Reporting) — COMPLIANCE VERIFICATION

| Requirement | Status | Evidence |
|---|---|---|
| Incident detection capability (24/7) | ✓ COMPLIANT | SOC team, SIEM monitoring |
| Identification of significant incidents | ✓ COMPLIANT | Severity matrix (Section 3.2) |
| Significant incident report within 24h | ✓ COMPLIANT | Process documented (Section 6.1) |
| Initial contact with competent authority | ✓ COMPLIANT | Email to cybersecurity@bka.gv.at |
| Competent authority contact details | ✓ COMPLIANT | Section 9.1 |
| Post-incident review (within 5 days) | ✓ COMPLIANT | Process documented (Section 5.4) |

### 11.2 Article 24 (Security Assessment) — COMPLIANCE PLAN

| Requirement | Status | Plan |
|---|---|---|
| Qualified security assessor | ⏳ PLANNED | Engage external auditor by Q3 2026 |
| Annual security assessment | ⏳ PLANNED | First assessment: July 15, 2026 |
| Assessment scope (Article 24(2)) | ✓ PLANNED | Technical + organizational measures |
| Assessment report | ⏳ PLANNED | Report to competent authority by August 31 |

---

## 12. TIMELINE & SIGN-OFF

### 12.1 Approval Chain

| Approver | Role | Deadline | Status |
|----------|------|----------|--------|
| **CISO** | Incident Response Program Owner | June 20 | ⏳ Pending |
| **General Counsel** | Legal Review | June 22 | ⏳ Pending |
| **Competent Authority** (Austria) | Regulatory Approval | June 30 | ⏳ Pending |

### 12.2 Implementation Readiness

- **Detection:** SIEM + alerting ready (deployed June 3)
- **Team:** Incident Response Team roster finalized
- **Procedures:** Response playbooks documented (this document)
- **Communication:** Templates prepared (Section 8)
- **Legal:** DPA + counsel review completed

**Status:** READY FOR APPROVAL

---

## APPENDIX A: INCIDENT TRACKING TEMPLATE

```
INCIDENT TICKET TEMPLATE

INCIDENT ID: INC-2026-0001
INCIDENT NAME: [Descriptive name]
DATE OPENED: [Date/Time]
SEVERITY: [CRITICAL | HIGH | MEDIUM | LOW]

DESCRIPTION:
[What happened? Be specific and technical.]

DETECTION METHOD:
[How was this discovered? (Alert, manual, customer report?)]

CUSTOMERS AFFECTED:
- Customer A (est. 100 data subjects)
- Customer B (est. 50 data subjects)

SYSTEMS AFFECTED:
- System 1
- System 2

ACTIONS TAKEN:
1. [Action] - [Time] - [Owner]
2. [Action] - [Time] - [Owner]

INVESTIGATION FINDINGS:
[Root cause, impact assessment, scope]

REMEDIATION PLAN:
[Specific steps to fix and prevent recurrence]

TIMELINE TO RESOLUTION:
[Estimated completion time for each step]

REGULATORY NOTIFICATIONS REQUIRED:
- [ ] NIS2 (competent authority)
- [ ] GDPR (DPA)
- [ ] Customer notification

POST-INCIDENT REVIEW SCHEDULED:
[Date/Time]

STATUS:
[ ] Open / In Progress
[ ] Under Investigation
[ ] Remediation In Progress
[ ] Resolved (awaiting PIR)
[ ] Closed

OWNER: [Incident Commander Name]
NEXT UPDATE: [Date/Time]
```

---

**END OF NIS2 INCIDENT RESPONSE PLAN**

**Document Status:** Ready for Competent Authority Approval  
**Next Steps:**
1. Finalize CISO sign-off (target June 20)
2. Send to Austrian Bundeskanzleramt for regulatory acknowledgment (target June 25)
3. Publish summary on company website (target June 30)
4. Conduct first quarterly tabletop exercise (target July 1)

**Maintained By:** Security & Compliance Team  
**Last Updated:** June 4, 2026  
**Review Cycle:** Quarterly (with annual update)

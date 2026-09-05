# Phase 3 Enterprise Hardening Architecture
## Comprehensive Design Document (Jun 2027 - May 2028)

**Document Version:** 1.0 (Sep 5, 2026)  
**Status:** Architecture Design - Ready for Implementation Planning  
**Timeline:** Jun 2027 - May 2028 (12 months)  
**Budget Estimate:** €1.8M (hardware €600K, engineering €1.2M)

---

## Executive Summary

Phase 3 transforms SovereignNexus from a pilot-stage sovereign AI platform into a production-grade enterprise system. Building on Phase 1's 11-layer harness (May 2027) and Phase 2's multi-agent orchestration (Dec 2027), Phase 3 delivers:

- **6 Enterprise Systems** (1,500+ LOC each, fully tested)
- **Zero-trust architecture** with PBFT consensus for 3-of-5 agent agreement
- **Regulatory compliance automation** (EU AI Act, Basel III, SOC 2)
- **Advanced threat detection** with real-time anomaly detection and forensic logging
- **SaaS-ready multi-tenancy** supporting 1000+ customers
- **Production operations** with 99.99% uptime SLA

### Competitive Advantage
- **Hands-on-silicon compliance:** Every design component verified via MMV Protocol in live environment
- **Cryptographic audit trail:** All compliance decisions signed and immutable
- **Fail-closed defaults:** Deny-by-default authorization, real-time veto gates
- **Hardware-aware optimization:** Target Jetson Thor (128GB, 72 TFLOPS) + Arm-based edge deployments

### Phase 3 Success Criteria (May 31, 2028)
- ✅ Enterprise auth passes SAML 2.0 / OAuth 2.0 certification (third-party audit)
- ✅ Compliance reports auto-generated for EU AI Act, Basel III, SOC 2 (signed PDFs)
- ✅ Threat detection model: 95%+ anomaly detection accuracy on 10k+ test events
- ✅ 1000+ multi-tenant environments provisioned and tested
- ✅ 99.99% uptime SLA maintained over 6-month production run
- ✅ Cost-per-deployment reduced to €150/month (down from €500 Phase 2)

---

## System 1: Enterprise Authentication & Authorization

### Design Overview

**Scope:** Multi-protocol authentication (SAML 2.0, OAuth 2.0, OIDC) + MFA (TOTP, WebAuthn) + role-based and attribute-based access control (RBAC + ABAC).

**Current State (Phase 2 End):**
- `siss-vault-integration` — KMS layer with Ed25519 key management
- `siss-zero-trust` — Basic zero-trust framework (526 LOC)
- `l3-permit-gates` — Tool whitelisting (gVisor sandbox)

**Gap Analysis:**
- No SAML 2.0 IdP integration
- No OAuth 2.0 provider (GitHub, Google, Azure AD)
- No MFA enforcement policy
- No session management across multi-tenant environments
- No JWT + PASETO token support for service-to-service auth

### Architecture Design

#### 1.1 SAML 2.0 Integration Layer

**Component:** `siss-saml-provider` (300 LOC)

```
Enterprise IdP (Okta/Azure AD/OneLogin)
    ↓
siss-saml-provider::metadata()      [generate SP metadata]
    ↓
IdP signs SAML assertion
    ↓
siss-saml-provider::validate()      [verify signature via x509 cert]
    ↓
siss-saml-provider::attribute_mapper()  [map SAML attributes → internal claims]
    ↓
siss-vault-integration::store_session()  [persist session + MFA state]
    ↓
JWT issued to client (expires 1hr, refresh: 24hr)
```

**Key Components:**
- **Metadata Endpoint:** `/auth/saml/metadata` — returns ServiceProvider descriptor (SP metadata)
- **Assertion Consumer Service (ACS):** `/auth/saml/acs` — accepts signed SAML assertions
- **Signature Verification:** x509 certificate chain validation (against IdP public cert from metadata)
- **Attribute Mapping:** SAML attributes → internal claims (email, groups, roles)
- **Session Persistence:** Store in `siss-vault-integration` with MFA state machine

**Integration Points:**
- `siss-vault-integration::PKI` — Manage IdP certificates
- `l3-permit-gates` — Enforce RBAC based on mapped groups
- `siss-event-log` — Log all SAML assertions (for forensics)

**Testing Strategy:**
- Unit: SAML assertion validation (valid, expired, unsigned, tampered)
- Integration: End-to-end SAML flow with mock IdP (pysaml2 in test harness)
- MMV: Click "Login with Okta" → redirect to IdP → assert with groups → land in dashboard

#### 1.2 OAuth 2.0 / OIDC Provider

**Component:** `siss-oauth-server` (400 LOC)

```
Scenario A: User Login (Authorization Code Flow)
┌─────────────┐
│   Browser   │ → GET /auth/authorize?client_id=...&redirect_uri=...&scope=openid+profile
└─────────────┘
    ↓
siss-oauth-server::authorize()       [display consent screen]
    ↓
User approves scopes
    ↓
siss-oauth-server::code_grant()      [issue authorization code (2-min expiry)]
    ↓
Redirect to client_redirect_uri?code=...
    ↓
Client backend:
  POST /auth/token {code, client_id, client_secret}
    ↓
siss-oauth-server::token_exchange()  [verify code + secret, issue JWT + refresh]
    ↓
Client stores JWT, uses for API calls (Authorization: Bearer <jwt>)

Scenario B: Service-to-Service (Client Credentials)
┌──────────────────────┐
│ Microservice A       │ → POST /auth/token {client_id, client_secret, grant_type=client_credentials}
└──────────────────────┘
    ↓
siss-oauth-server::validate_credentials()  [verify secret via vault]
    ↓
siss-oauth-server::mint_jwt()       [issue service JWT (24hr expiry)]
    ↓
Token returned → Microservice B verifies signature
```

**Key Components:**
- **Authorization Endpoint:** `/auth/authorize` — user consent, PKCE support
- **Token Endpoint:** `/auth/token` — code exchange, refresh, client credentials
- **UserInfo Endpoint:** `/auth/userinfo` — return claims for logged-in user
- **JWKS Endpoint:** `/.well-known/jwks.json` — public keys for client signature verification
- **Revocation Endpoint:** `/auth/revoke` — invalidate tokens immediately
- **Introspection Endpoint:** `/auth/introspect` — check token validity + claims

**Token Design:**
```
JWT Header:  {"alg": "EdDSA", "kid": "<key_id>"}
JWT Payload: {
  "iss": "https://smaos.sn/auth",
  "sub": "<user_id>",
  "aud": "<client_id>",
  "exp": <unix_timestamp>,
  "iat": <unix_timestamp>,
  "scope": "openid profile email",
  "tenant_id": "<tenant_uuid>",
  "groups": ["admin", "compliance-officer"],
  "acr": "urn:mace:incommon:iap:silver"  [assurance level]
}
JWT Signature: EdDSA (PQC-resistant via Ed25519)
```

**Integration Points:**
- `siss-vault-integration::store_oauth_credentials()` — Client secrets + IdP certs
- `l3-permit-gates::validate_scopes()` — Enforce scope-to-capability mapping
- `siss-behavioral-firewall::rate_limit_token_endpoint()` — Prevent brute-force
- `l8-proof::sign_token_mint()` — Cryptographic proof of token issuance (ledger entry)

**Testing Strategy:**
- Unit: Authorization code flow, refresh token rotation, invalid client rejection
- Integration: Client app (React) → OAuth server → verified JWT → API access
- MMV: Login via Google → consent screen → lands in app → API call shows user email

#### 1.3 Multi-Factor Authentication (MFA)

**Component:** `siss-mfa-orchestrator` (250 LOC)

```
Post-SAML/OAuth Authentication:

1. Check MFA Requirement
   ├─ Policy: require_mfa = true for admins, false for users
   ├─ Device: is_trusted_device = cache[device_id] ? false : true
   └─ Risk: anomaly_score(login_ip, login_device) > 0.7 → force MFA

2. MFA Challenge Selection
   ├─ TOTP (Authenticator App) — Primary
   ├─ WebAuthn (FIDO2/U2F) — Hardware token fallback
   └─ Email OTP — Fallback (6-digit, 10-min expiry)

3. TOTP Verification
   POST /auth/mfa/verify {totp_code}
   ├─ Validate against HMAC-SHA1(secret, current_time_window)
   ├─ Prevent replay: cache verified codes (30s window)
   └─ Log attempt (fail after 5 retries)

4. WebAuthn Verification
   GET /auth/mfa/webauthn/challenge
   ├─ Generate random challenge (32 bytes)
   ├─ Store in session with 2-min expiry
   └─ Return {challenge, rp_id, timeout}
   
   POST /auth/mfa/webauthn/verify {clientDataJSON, attestationObject}
   ├─ Verify signature against stored public key
   ├─ Check challenge matches
   └─ Increment counter (prevent cloning attacks)

5. Session Upgrade
   siss-vault-integration::mark_mfa_verified(session_id, mfa_method)
   ├─ Set auth_context.mfa_verified = true
   ├─ Set auth_context.mfa_method = "TOTP" | "WEBAUTHN"
   └─ Issue new JWT with higher ACR (assurance level)
```

**MFA Policy Engine:**

```rust
struct MFAPolicy {
  require_for_roles: Vec<String>,  // ["admin", "compliance-officer"]
  require_for_actions: Vec<String>,  // ["authorize_payment", "revoke_cert"]
  risk_threshold: f32,  // 0.7 → trigger MFA if anomaly score > 0.7
  trust_device_duration: Duration,  // 30 days
  totp_window: i32,  // ±1 window (current + prev/next 30s)
  webauthn_timeout: Duration,  // 60s
  otp_delivery: DeliveryMethod,  // Email, SMS (if available)
}
```

**Integration Points:**
- `siss-behavioral-firewall::risk_score()` — Anomaly detection for adaptive MFA
- `siss-vault-integration::store_totp_secret()` — Encrypted TOTP seed storage
- `siss-event-log::log_mfa_attempt()` — All MFA events (pass/fail, method, IP)

#### 1.4 Session Management & Revocation

**Component:** `siss-session-manager` (200 LOC)

```
Session Lifecycle:

CREATE:
  POST /auth/login {saml_assertion | oauth_code}
  → validate auth
  → check MFA requirement
  → if MFA required: create pending_session (2-min TTL), ask for MFA code
  → if MFA verified or not required: create authenticated_session
    ├─ session_id = uuid()
    ├─ user_id = <from assertion/token>
    ├─ tenant_id = <from session or assertion>
    ├─ roles = [from mapped attributes]
    ├─ issued_at = now()
    ├─ expires_at = now() + 1h (access token lifetime)
    ├─ mfa_verified = true/false
    ├─ device_id = hash(user_agent + ip_address)
    └─ Store in siss-vault-integration::sessions

VALIDATE (on every API request):
  Header: Authorization: Bearer <jwt>
  → siss-vault-integration::validate_jwt(<jwt>)
  → verify signature (EdDSA)
  → check expiry
  → check revocation list (bloom filter for performance)
  → extract claims → inject into request context

REFRESH:
  POST /auth/refresh {refresh_token}
  → validate refresh_token (separate 24hr TTL)
  → if age > 12h: require MFA re-verification
  → mint new access_token
  → optionally rotate refresh_token (CSRF mitigation)

REVOKE:
  POST /auth/revoke {token_or_session_id}
  → add token to revocation list (distributed cache)
  → logout all sessions if user account compromised
  → log revocation event (timestamp + reason)

LOGOUT:
  DELETE /auth/sessions/{session_id}
  → remove from active session store
  → invalidate all related tokens
  → clear OIDC session (if SAML-initiated logout)
```

**Session Storage:**
- **Active Sessions:** Redis (in-memory) with 1-hour TTL
  - Key: `session:{session_id}`
  - Value: JSON with user_id, tenant_id, roles, MFA state
  - Failover: PostgreSQL (backup)
- **Revocation List:** Bloom filter (Redis) + event log
  - Key: `revoked_tokens:{hour}`
  - Value: bitset of revoked JWT sub claims
  - Compact: 1 bloom filter per hour (prevents memory explosion)

**Testing Strategy:**
- Unit: Session creation, expiry, refresh token rotation
- Integration: Login → get JWT → use for API → logout → verify revoked
- MMV: Browser login → check Authorization header in DevTools → after logout, API returns 401

#### 1.5 Integration Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Auth Orchestration Layer                 │
│                  (siss-auth-orchestrator)                   │
├────────────────────────────────────────────────────────────┤
│  ┌─────────────┬──────────────┬─────────────────────────┐  │
│  │   SAML      │    OAuth2    │   MFA Orchestrator      │  │
│  │ Provider    │    Server    │   (TOTP, WebAuthn)      │  │
│  └────────────┬───────────────┴──────────────┬──────────┘  │
│               │                              │             │
│  ┌────────────▼──────────────────────────────▼──────────┐  │
│  │         Session Manager (Redis + PostgreSQL)         │  │
│  │     (Create, Validate, Refresh, Revoke)              │  │
│  └────────────┬─────────────────────────────────────────┘  │
│               │                                             │
└───────────────┼─────────────────────────────────────────────┘
                │
    ┌───────────┴────────────┬──────────────────────────┐
    │                        │                          │
    ▼                        ▼                          ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Vault Integration│  │ Behavioral       │  │ Event Log        │
│ (Key Storage)    │  │ Firewall (Risk)  │  │ (Forensics)      │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

**API Surface:**

```
POST /auth/saml/metadata                          → SP metadata
POST /auth/saml/acs                               → SAML assertion consumer
GET  /auth/authorize                              → OAuth authorization endpoint
POST /auth/token                                  → Token exchange/refresh
GET  /auth/userinfo                               → Claims for current user
GET  /.well-known/jwks.json                       → Public signing keys
POST /auth/mfa/verify                             → TOTP/OTP verification
GET  /auth/mfa/webauthn/challenge                 → WebAuthn challenge
POST /auth/mfa/webauthn/verify                    → WebAuthn response
POST /auth/revoke                                 → Revoke token/session
DELETE /auth/sessions/{session_id}                → Logout
POST /auth/refresh                                → Refresh access token
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Foundation**
- SAML 2.0 provider (complete validation, ACS endpoint)
- OAuth 2.0 server (auth code flow, token endpoint, JWKS)
- Session manager (Redis + PostgreSQL)
- Deliverable: All 3 components unit + integration tested

**Phase 3b (Aug-Sep 2027): MFA & Advanced Features**
- TOTP orchestrator + device trust
- WebAuthn support (FIDO2)
- Risk-based adaptive MFA
- Deliverable: MMV walkthrough of MFA flow for each method

**Phase 3c (Oct 2027): Integration & Hardening**
- End-to-end auth orchestration
- Revocation list optimization (bloom filters)
- Load testing (10k concurrent sessions)
- Deliverable: Performance SLA <50ms p99 latency

**Phase 3d (Nov-Dec 2027): Compliance & Security Review**
- SAML 2.0 audit (third-party)
- OAuth 2.0 security audit (OWASP)
- Threat modeling (authentication bypass, token hijacking)
- Deliverable: Audit report + remediation evidence

---

## System 2: Compliance Reporting Automation

### Design Overview

**Scope:** Auto-generate regulatory reports (EU AI Act, Basel III, SOC 2) + maintain audit trail + produce signed compliance certificates.

**Current State (Phase 2 End):**
- `siss-eu-compliance` — AI Act analyzer, GDPR mapper, NIS2 enforcer, ISO27001 audit, TISAX validator, SOC2 attestation (1000+ LOC)
- `siss-regulatory-reporter` — Report generation framework
- `l9-governance-api` — Policy registry (governance rules)
- `l8-proof` — Merkle ledger for cryptographic audit trail

**Gap Analysis:**
- No automated report scheduling (monthly/quarterly/annual)
- No PDF/JSON export with KMS signatures
- No compliance gap detection (what controls are missing?)
- No real-time metric collection from system components
- No multi-framework cross-mapping (EU AI Act + Basel III + SOC 2 alignment)

### Architecture Design

#### 2.1 Compliance Data Collection Engine

**Component:** `siss-compliance-collector` (350 LOC)

```
Continuous Collection (hourly):

┌─────────────────────────────────────────────────────┐
│  Compliance Data Sources                            │
├─────────────────────────────────────────────────────┤
│  • siss-behavioral-firewall::metrics()              │
│    → egress denials, policy violations              │
│  • siss-event-log::query(framework_tag)             │
│    → authorization attempts, veto triggers          │
│  • l3-permit-gates::get_enforcement_stats()         │
│    → tool whitelisting hits/misses                  │
│  • siss-ai-factory::model_audit_trail()             │
│    → model deployments, inference logs              │
│  • siss-vault-integration::key_rotation_log()       │
│    → cryptographic key lifecycle events             │
│  • siss-observability::hardware_metrics()           │
│    → CPU, memory, network (for resource compliance) │
│  • l8-proof::ledger_entries()                       │
│    → authorization decisions (for audit trail)      │
└─────────────────────────────────────────────────────┘
        ↓
siss-compliance-collector::aggregate()
├─ Fetch metrics from all sources (parallel queries)
├─ Normalize to standard schema
├─ Tag with source + framework + control ID
└─ Write to time-series database (pgvector + TSV)

Storage:
  compliance_events {
    id: uuid,
    timestamp: datetime,
    framework: enum(EU_AI_ACT, BASEL_III, SOC_2, GDPR, NIS2),
    control_id: string,          // "EU-AI-ACT-6.1" | "BASEL-III-CET1"
    event_type: enum(PASS, FAIL, DEVIATION, REMEDIATION),
    details: jsonb,              // {metric_value, threshold, source}
    proof_hash: string,          // reference to l8-proof ledger entry
    signed_at: datetime,
    signature: bytes,            // Ed25519 signature (KMS)
  }
```

**Control Mapping Examples:**

| Framework | Control ID | Metric | Source | Threshold |
|-----------|-----------|--------|--------|-----------|
| EU AI Act | 6.1 | Inference audit trail logged | siss-event-log | 100% of inferences |
| EU AI Act | 6.3 | Model transparency card present | siss-ai-factory | all deployed models |
| Basel III | CET1 | Common Equity Tier 1 ratio | siss-observability::capital_calculation() | ≥10.5% |
| Basel III | LIQ | Liquidity coverage ratio | siss-observability::liquidity_monitor() | ≥100% |
| SOC 2 | CC6.1 | Logical access controls | l3-permit-gates | all tools gated |
| SOC 2 | AU2.1 | User activity monitored | siss-event-log | 100% of actions logged |

**Testing Strategy:**
- Unit: Metric aggregation (normalize different schemas)
- Integration: Trigger compliance event → verify collected in time-series DB
- MMV: Query compliance events via dashboard → verify all sources reporting

#### 2.2 Compliance Analyzer & Gap Detector

**Component:** `siss-compliance-analyzer` (300 LOC)

```
Analysis Loop (daily at 23:00 UTC):

1. Load all collected events (last 30 days)
2. For each framework (EU AI Act, Basel III, SOC 2):
   a. Group by control_id
   b. Calculate compliance_score = (pass_count / (pass_count + fail_count))
   c. Flag gaps: score < threshold (e.g., 95% for critical controls)
   d. Trend analysis: is score improving/degrading?
3. Generate compliance_report {
     framework: string,
     report_period: (start_date, end_date),
     overall_score: float (0-100),
     controls: [
       {
         control_id: string,
         status: enum(COMPLIANT, MINOR_DEVIATION, NON_COMPLIANT),
         score: float,
         events_count: int,
         gap_summary: string,
         remediation_due: datetime,
       }
     ],
     gaps: [  # controls with score < 95%
       {
         control_id: string,
         gap_description: string,
         evidence_count: int,
         recommended_action: string,
       }
     ],
   }
4. Store report in PostgreSQL + sign with KMS
5. Alert compliance team if score drops > 5% from previous period
6. Trigger remediation workflow (if gaps detected)
```

**Compliance Score Calculation:**

```
OVERALL_SCORE = weighted_average([
  framework_score(EU_AI_ACT) * 0.4,      // 40% weight (primary reg)
  framework_score(BASEL_III) * 0.3,      // 30% weight (financial)
  framework_score(SOC_2) * 0.2,          // 20% weight (operational)
  framework_score(GDPR) * 0.1,           // 10% weight (data protection)
])

framework_score(f) = mean([
  control_score(c) for c in critical_controls(f)
])

control_score(c) = {
  if (events_where_status=PASS for c) / total_events(c) > 0.95:
    100.0 - min(5.0, penalties_for_c)
  else:
    (pass_count / total_count) * 100.0
}
```

**Gap Remediation Workflow:**

```
Gap Detected: EU-AI-ACT-6.1 (Inference logging)

Event: siss-observability detected inference logging disabled
→ siss-compliance-analyzer::detect_gap()
→ Create remediation_ticket {
     gap_id: "gap_20270815_001",
     framework: "EU_AI_ACT",
     control_id: "6.1",
     severity: "HIGH",
     gap_description: "Model inference logging disabled on 3 endpoints",
     evidence: [inference logs showing gaps],
     remediation_plan: [
       {step: "Re-enable logging on endpoints", owner: "ops-team", due: "2027-08-16"},
       {step: "Verify logs flowing", owner: "compliance-officer", due: "2027-08-16"},
       {step: "Generate backfill proof", owner: "audit", due: "2027-08-17"},
     ]
   }
→ Assign to compliance_officer (via siss-a2a-dispatcher)
→ If not resolved in 48h: escalate to legal
```

#### 2.3 Compliance Report Generator

**Component:** `siss-report-generator` (250 LOC)

```
Report Generation (on-demand or scheduled):

INPUT:  compliance_analyzer::output (report)
OUTPUT: PDF + JSON + signed certificate (KMS signature)

┌──────────────────────────────────────────────┐
│ Report Format: PDF (15-20 pages)              │
├──────────────────────────────────────────────┤
│ Page 1:  Cover page + executive summary      │
│          Overall compliance score + trend    │
│          Period + signature                  │
│                                               │
│ Pages 2-4: EU AI Act Compliance               │
│           • Risk classification + proof       │
│           • Model cards (transparency)        │
│           • Human oversight audit trail       │
│           • Gaps + remediation status         │
│                                               │
│ Pages 5-7: Basel III Compliance               │
│           • Capital adequacy (CET1, Tier 2)   │
│           • Leverage ratio                    │
│           • Liquidity coverage ratio          │
│           • Counterparty risk summary         │
│                                               │
│ Pages 8-10: SOC 2 Compliance                  │
│            • Logical access controls          │
│            • Monitoring + alerting            │
│            • Change management                │
│            • Incident response                │
│                                               │
│ Pages 11-13: GDPR Data Processing             │
│             • Processing activities           │
│             • Data subject rights             │
│             • DPA status                      │
│             • DPIA results                    │
│                                               │
│ Pages 14-15: Audit Trail (hash chain)         │
│             • Merkle root (from l8-proof)     │
│             • Ledger entries (KMS signed)     │
│             • Forensic log (sample)           │
│                                               │
│ Back page: Certificate of Compliance          │
│           • Signed by: [KMS key_id]          │
│           • Timestamp + signature             │
│           • Verification URL                  │
└──────────────────────────────────────────────┘

PDF Generation Pipeline:
  report (JSON)
    ↓
  template_engine::render(template, report)  [Jinja2 or similar]
    ↓
  html_to_pdf::convert(html)  [wkhtmltopdf or Chromium]
    ↓
  pdf_document (unsigned)
    ↓
  siss-vault-integration::sign_pdf(document, kms_key)
    ↓
  pdf_document (signed with KMS signature + timestamp)
```

**JSON Report Schema:**

```json
{
  "report_id": "report_20270831_001",
  "generated_at": "2027-08-31T23:00:00Z",
  "period": {
    "start": "2027-08-01T00:00:00Z",
    "end": "2027-08-31T23:59:59Z"
  },
  "overall_score": 96.5,
  "score_trend": {
    "previous_period": 95.2,
    "change_percentage": 1.3,
    "direction": "improving"
  },
  "frameworks": {
    "eu_ai_act": {
      "score": 98.0,
      "status": "COMPLIANT",
      "controls_evaluated": 45,
      "controls_passing": 44,
      "critical_gaps": []
    },
    "basel_iii": {
      "score": 94.0,
      "status": "MINOR_DEVIATION",
      "cet1_ratio": 11.2,
      "liquidity_coverage": 105.3,
      "gaps": [
        {
          "control_id": "LEVERAGE",
          "description": "Leverage ratio monitoring inactive on 1 region",
          "remediation_due": "2027-09-07"
        }
      ]
    },
    "soc_2": {
      "score": 97.0,
      "status": "COMPLIANT",
      "controls_passing": 28,
      "controls_evaluated": 29
    }
  },
  "audit_trail": {
    "ledger_root": "0x3a4f...",
    "ledger_entries_count": 52341,
    "merkle_proof": "0x7b2f...",
    "proof_timestamp": "2027-08-31T23:00:00Z"
  },
  "signature": {
    "algorithm": "Ed25519",
    "key_id": "kms_key_20270601_001",
    "signature_value": "0x9e2d...",
    "signed_at": "2027-08-31T23:00:05Z"
  }
}
```

**Report Distribution:**

```
Generated Report
    ↓
siss-compliance-reporter::distribute()
    ├─ Archive in S3 (encrypted, 7-year retention)
    ├─ Email to compliance_team@smaos.sn (PDF + JSON)
    ├─ POST to regulatory_portal API (if required)
    ├─ Publish to public-facing compliance dashboard (anonymized)
    └─ Trigger webhook for external audit systems
```

#### 2.4 Multi-Framework Cross-Mapping

**Component:** `siss-framework-mapper` (200 LOC)

```
Purpose: Show how SMAOS controls satisfy multiple frameworks simultaneously

Example Mapping:

┌─────────────────┬──────────────────┬──────────────────┬────────────────┐
│ Control Area    │ EU AI Act        │ Basel III        │ SOC 2          │
├─────────────────┼──────────────────┼──────────────────┼────────────────┤
│ Model Monitoring│ Art. 6.3 (Logging)│ Art. 132 (Risk) │ CC6.2 (Audit)  │
│                 │ → siss-event-log │ → Credit risk   │ → All logs     │
│                 │ → verify 100%    │   assessment    │   indexed,     │
│                 │   inference log  │   models        │   searchable    │
│                 │                  │   → real-time   │                │
│                 │                  │   model monitor │                │
├─────────────────┼──────────────────┼──────────────────┼────────────────┤
│ Human Oversight │ Art. 24 (H-in-L) │ Art. 8 (Gov.)   │ A1.2 (Mgmt)    │
│                 │ → veto gates     │ → Board review  │ → auth log     │
│                 │ → 100% >€1M      │   of decisions  │   of all ops   │
│                 │ → signed auth    │   → l8-proof    │   → l8-proof   │
├─────────────────┼──────────────────┼──────────────────┼────────────────┤
│ Data Security   │ Art. 15 (Tech)   │ Art. 163 (Data)  │ CC6.1 (Access) │
│                 │ → Encryption     │ → Backup        │ → MFA required │
│                 │ → siss-vault     │   → 3-copies    │   → all access │
│                 │   (KMS)          │   → recovery    │   → siss-zero- │
│                 │                  │   → RTO<1h      │   trust        │
└─────────────────┴──────────────────┴──────────────────┴────────────────┘

Cross-Mapping Algorithm:
  for each control_area:
    collect([eu_ai_act_control, basel_iii_control, soc2_control])
    find_overlapping_evidence(technical_implementations)
    generate_mapping_report("One control satisfies 3 frameworks")
    reduce_assessment_burden (auditors re-use evidence)
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Data Collection**
- Compliance collector (7 data sources)
- Real-time event tagging (all frameworks)
- Time-series database schema
- Deliverable: 30 days of compliance data collected

**Phase 3b (Aug-Sep 2027): Analysis & Reporting**
- Compliance analyzer (gap detection)
- Report generator (PDF + JSON + signed)
- Framework mapper (cross-mapping)
- Deliverable: First monthly compliance report (signed, verified)

**Phase 3c (Oct 2027): Automation & Scheduling**
- Scheduled report generation (monthly/quarterly)
- Alert system (gaps, trend changes)
- Regulatory portal API integration
- Deliverable: Reports auto-generated on schedule

**Phase 3d (Nov-Dec 2027): Verification & Integration**
- MMV: Generate EU AI Act report → verify PDF → check signature
- Audit trail validation (all events signed by KMS)
- Performance testing (1000+ events/hour ingestion)
- Deliverable: Compliance reports ready for external audit

---

## System 3: Advanced Threat Detection

### Design Overview

**Scope:** Real-time behavioral anomaly detection + intrusion detection + forensic logging.

**Current State (Phase 2 End):**
- `siss-behavioral-firewall` — Egress policy enforcement (event logging capability)
- `siss-event-log` — Event storage + forensic query
- `siss-consensus-monitor` — Peer discovery + validation
- No ML-based anomaly detection

**Gap Analysis:**
- No trained anomaly detection model
- No real-time alert system
- No forensic visualization (attack timeline)
- No automated incident response playbooks
- No threat intelligence integration (IP reputation, etc.)

### Architecture Design

#### 3.1 Behavioral Anomaly Detector

**Component:** `siss-anomaly-detector` (400 LOC Rust + 300 LOC Python model)

```
Real-Time Anomaly Detection Pipeline:

┌────────────────────────────────────────────┐
│         Event Stream (from siss-event-log) │
├────────────────────────────────────────────┤
│ • User login attempts (IP, timestamp, UA)  │
│ • API calls (endpoint, method, user, size) │
│ • Tool invocations (tool_id, params)       │
│ • Model inferences (model_id, latency)     │
│ • Authorization events (decision, scope)   │
└────────────────────────────────────────────┘
        ↓
siss-anomaly-detector::extract_features()
├─ Temporal features:
│   • Time since last login (same IP)
│   • API call frequency (per user, per hour)
│   • Tool invocation rate (per user, per tool)
│
├─ Network features:
│   • IP geolocation (rapid travel?)
│   • ASN (unexpected ISP?)
│   • Port usage (non-standard?)
│
├─ Behavioral features:
│   • Tools never used before by this user
│   • API endpoint never hit before
│   • Large payload (data exfiltration indicator?)
│   • Unusual time-of-day activity
│
└─ Statistical features:
    • Z-score vs. user's own baseline
    • Z-score vs. peer group (role-based)
    • Entropy of endpoint access patterns

Storage: Feature vectors in Redis (real-time) + PostgreSQL (batch)
```

**ML Model Architecture:**

```
Training Data:
  • 10,000+ hours of production logs (Phase 1-2)
  • Labeled events (normal vs. anomalous)
  • Anomalies: unauthorized tool access, data exfiltration attempts, privilege escalation

Model: Isolation Forest + One-Class SVM (ensemble)
  Input: Feature vector (45-dimensional)
  Output: Anomaly score (0.0-1.0)

Training Pipeline:
  Phase 3a: Collect 30 days of Phase 2 logs
  Phase 3a: Label anomalies (manual + rule-based detection)
  Phase 3b: Train model (scikit-learn)
  Phase 3b: Evaluate on holdout test set (precision 96%, recall 91%)
  Phase 3c: Deploy to production (canary: 5% traffic)
  Phase 3d: Monitor false positive rate (target < 0.1%)

Real-Time Scoring:
  New event arrives
  → Extract 45-dimensional feature vector (< 10ms)
  → Load model from Redis cache
  → Score = model.predict(features)
  → If score > 0.75: flag as anomaly
  → Store event + score in PostgreSQL
```

**Anomaly Alert System:**

```
Event Score > 0.75 (anomalous)
    ↓
siss-anomaly-detector::classify()
    ├─ severity = HIGH/MEDIUM/LOW
    │   • HIGH: privilege escalation, data exfiltration (score > 0.9)
    │   • MEDIUM: unusual tool access (score 0.75-0.9)
    │   • LOW: minor behavioral deviation (score 0.6-0.75)
    │
    ├─ anomaly_type = {
    │     UNAUTHORIZED_TOOL_ACCESS,
    │     DATA_EXFILTRATION,
    │     PRIVILEGE_ESCALATION,
    │     INSIDER_THREAT,
    │     BRUTE_FORCE,
    │     DDoS,
    │     MALWARE,
    │   }
    │
    └─ recommended_action = {
         BLOCK,        // block user/IP immediately
         CHALLENGE,    // require MFA
         ALERT,        // notify sec ops
         INVESTIGATE,  // flag for manual review
       }

Alert Routing:
  Severity HIGH    → PagerDuty (immediate)
               + Block IP in siss-behavioral-firewall
               + Revoke active sessions
               
  Severity MEDIUM  → Slack #security channel
               + Log to event audit trail
               
  Severity LOW     → Email daily digest
               + Store for trending analysis
```

#### 3.2 Intrusion Detection System (IDS)

**Component:** `siss-intrusion-detector` (250 LOC)

```
Signature-Based Detection:

Known Attack Patterns:
  • SQL injection: regex on API parameters
  • Path traversal: ../ in URL paths
  • Command injection: shell metacharacters in tool params
  • XXE: XML entity definitions
  • CSRF: cross-site request forgery (token mismatch)

Real-time Pattern Matching:
  Incoming request
    ↓
  siss-intrusion-detector::scan_signatures()
    ├─ Check all 20+ OWASP Top 10 patterns
    ├─ Log any matches (even if benign)
    └─ If HIGH confidence match: block + alert

Example: SQL Injection Detection
  Tool: "query_database"
  Param: "SELECT * FROM users WHERE id = '<user_input>'"
  user_input = "1' OR '1'='1"
    ↓
  Pattern: /' OR '.*'='.*'/ matches
    ↓
  siss-intrusion-detector::assess_risk()
    ├─ Context: Is this user known to run complex queries? (ML score)
    ├─ Baseline: First time this exact pattern for this user?
    └─ Risk score = 0.92 (HIGH)
    ↓
  Action: BLOCK + Log + Alert
```

**Network-Based Detection:**

```
Anomalous Network Behavior:
  • Port scanning (multiple ports from single IP)
  • DDoS indicators (sudden spike in requests)
  • DNS exfiltration (unusual query patterns)
  • Slow brute-force (spread over days)

Detection via siss-event-log analysis:
  Aggregate events by (source_ip, time_window)
    ↓
  Calculate request_rate(ip)
  If request_rate > 10k/sec: DDoS indicator
    ↓
  siss-behavioral-firewall::rate_limit()
    ├─ Throttle IP to 100 req/sec
    ├─ Issue CAPTCHA challenge
    └─ Log source IP + ASN
```

#### 3.3 Forensic Investigation & Incident Response

**Component:** `siss-forensics-engine` (300 LOC)

```
Incident Investigation Timeline:

User: alice@company.com
Incident: Unauthorized model inference (scored anomaly 0.94)
Discovery: 2027-08-31 14:32:15 UTC

Investigation:
  siss-forensics-engine::build_timeline(user_id, incident_time_window)
    ↓
  Query siss-event-log for all events related to alice
    ├─ Past 24 hours: 342 events
    ├─ Last 30 days: 8,901 events
    └─ Focus: 10 minutes before to 1 hour after incident
    
  Build incident graph:
    1. 14:30:00 - alice logs in from IP 185.220.X.X (Tor exit node)
       → Baseline: alice always logs from 203.0.113.X (office)
       → Risk: NEW_IP + TOR (score 0.88)
    
    2. 14:31:00 - Failed 2FA attempt (wrong TOTP code)
       → Baseline: alice never fails auth
       → Risk: MFA_BYPASS_ATTEMPT (score 0.92)
    
    3. 14:31:45 - Successful login (session_id: sess_xyz)
       → Note: 2FA bypassed after 2 failures?
       → Risk: AUTH_ANOMALY (score 0.95)
    
    4. 14:32:00 - Access to model "gpt-4-finance-classifier"
       → Baseline: alice is compliance officer (shouldn't access models)
       → Risk: PRIVILEGE_ESCALATION (score 0.96)
    
    5. 14:32:15 - Unauthorized model inference
       → Input: Sensitive financial data (10 MiB)
       → Output: Model confidence + classification
       → Risk: DATA_EXFILTRATION (score 0.97)

Evidence Collection:
  ├─ Session token: sess_xyz (expired, revoked)
  ├─ API logs: 3 inference calls (endpoints logged)
  ├─ Model audit log: input/output data (10 MiB sensitivity)
  ├─ Merkle proof: l8-proof ledger entry (immutable timestamp)
  └─ Geographic evidence: 185.220.X.X ISP is PrivateInternetAccess

Incident Report:
  {
    incident_id: "INC_20270831_001",
    severity: "CRITICAL",
    user: "alice@company.com",
    user_role: "compliance-officer",
    auth_method: "SAML (Okta)",
    
    timeline: [
      {timestamp: "14:30:00", event: "login", ip: "185.220.X.X", risk_score: 0.88},
      {timestamp: "14:31:00", event: "mfa_fail", risk_score: 0.92},
      {timestamp: "14:32:00", event: "model_access", model: "gpt-4-finance", risk_score: 0.96},
      {timestamp: "14:32:15", event: "inference", data_volume: "10 MiB", risk_score: 0.97},
    ],
    
    indicators_of_compromise: [
      "TOR_EXIT_NODE_LOGIN",
      "MFA_BYPASS_ATTEMPT",
      "PRIVILEGE_ESCALATION",
      "LARGE_DATA_EXFILTRATION",
    ],
    
    recommended_actions: [
      "IMMEDIATE: Revoke all sessions for alice",
      "IMMEDIATE: Reset alice's password + TOTP seed",
      "WITHIN_1H: Notify data protection officer",
      "WITHIN_4H: Contact Okta for breach investigation",
      "WITHIN_24H: Forensic analysis of 10 MiB data exfiltrated",
    ],
    
    evidence_hash: "0x7f3a...",  // Merkle root of all forensic data
    evidence_signed_at: "2027-08-31T14:45:00Z",
    signed_by: "kms_key_20270601_incident",
  }
```

**Automated Incident Response Playbooks:**

```
Playbook: PRIVILEGE_ESCALATION Detected

Trigger: Anomaly score > 0.95 + type=PRIVILEGE_ESCALATION

Steps (executed atomically):
  1. Revoke all active sessions for affected_user (l8-proof::sign revocation)
  2. Send MFA reset challenge (require WebAuthn + email confirmation)
  3. Create incident ticket (assign to SOC team)
  4. Log to SIEM (syslog to security team)
  5. Optional: Lock account (if risk_score > 0.98)
  6. Notify user: "We've detected unusual activity. Please verify your account."
  7. Store full incident report (signed by KMS)
  8. Alert compliance_officer@smaos.sn

Execution Context:
  playbook_status = EXECUTING
  affected_user = alice@company.com
  affected_sessions = [sess_xyz]
  playbook_start_time = 2027-08-31 14:32:15
  playbook_end_time = 2027-08-31 14:32:45 (13 seconds total)
  
Verification:
  ✓ Sessions revoked (verified against Redis)
  ✓ MFA reset sent (email + SMS logged)
  ✓ Incident ticket created (INC_20270831_001)
  ✓ SIEM alert sent (timestamp logged)
  ✓ Full report signed (KMS signature attached)
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Data Collection & Model Training**
- Collect 30 days of production logs
- Label 10k+ events (anomalous vs. normal)
- Train isolation forest + SVM models
- Deliverable: Trained model (precision 96%, recall 91%)

**Phase 3b (Aug-Sep 2027): Real-Time Deployment**
- Deploy anomaly detector (Redis cache + PostgreSQL storage)
- Implement alert routing (PagerDuty, Slack, email)
- Build forensics engine (incident timeline)
- Deliverable: First incident report (signed, complete)

**Phase 3c (Oct 2027): Intrusion Detection**
- Deploy signature-based IDS
- Add network-based anomaly detection
- Integrate with siss-behavioral-firewall
- Deliverable: 20+ OWASP Top 10 patterns detected

**Phase 3d (Nov-Dec 2027): Incident Response Automation**
- Implement automated playbooks (10+ responses)
- Test end-to-end incident simulation
- MMV: Simulate attack → detect → response → verify forensics
- Deliverable: IR playbook documentation

---

## System 4: Customer Onboarding & Multi-Tenancy

### Design Overview

**Scope:** SaaS onboarding workflow + tenant isolation + multi-tenant governance.

**Current State (Phase 2 End):**
- `l9-governance-api` — Policy registry (tenant-scoped)
- No customer onboarding automation
- No tenant provisioning infrastructure

**Gap Analysis:**
- No self-service signup workflow
- No tenant namespace isolation (data, storage, compute)
- No per-tenant billing/usage tracking
- No multi-tenant role/permission boundaries
- No tenant-specific compliance settings

### Architecture Design

#### 4.1 Self-Service Customer Onboarding

**Component:** `siss-onboarding-service` (350 LOC)

```
Onboarding Workflow:

Step 1: Customer Registration
  ┌─────────────────────────────────────────┐
  │ https://smaos.sn/signup                  │
  │                                          │
  │ Form:                                     │
  │  • Company name (required)               │
  │  • Company email (@domain.com)           │
  │  • Admin name + phone                    │
  │  • Expected usage (low/medium/high)      │
  │  • Compliance requirements (checkboxes)  │
  │    - SOC 2 Type II                       │
  │    - EU AI Act                           │
  │    - Basel III                           │
  │    - GDPR DPA required                   │
  │  • Accept Terms of Service + DPA        │
  └─────────────────────────────────────────┘
  ↓
  siss-onboarding-service::validate_signup()
    ├─ Company email domain must be valid (MX record exists)
    ├─ Phone number must be valid (Twilio API)
    └─ No duplicate registrations (check email)
  ↓
  siss-onboarding-service::create_pending_customer()
    └─ Store in onboarding_queue (PostgreSQL)
    └─ NOT created as tenant yet
    └─ Send verification email (6-digit code, 1-hour expiry)

Step 2: Email Verification
  Customer receives email:
    "Verify your email: [link with code=ABC123]"
  ↓
  Customer clicks link
    ↓
  siss-onboarding-service::verify_email(code)
    ├─ Check code validity (not expired, correct)
    └─ Mark email as verified
    └─ Send next step (payment + contract)

Step 3: Trial or Payment Setup
  Option A: Free Trial (14 days)
    → siss-onboarding-service::start_trial()
    → Create trial_tenant (limited quotas)
    → Expiry: 14 days or usage limit exceeded
    
  Option B: Enterprise License
    → siss-onboarding-service::request_enterprise_contract()
    → Generate PDF contract (pre-filled with compliance reqs)
    → Send to legal_team@smaos.sn for review
    → Once signed: proceed to Step 4

Step 4: Tenant Provisioning
  siss-onboarding-service::provision_tenant()
    ├─ Create tenant {
         tenant_id = uuid(),
         company_name,
         email,
         created_at,
         trial_expiry: now() + 14 days (if trial),
         compliance_requirements: [SOC_2, EU_AI_ACT, ...],
         usage_quota: {
           inferences_per_month: 1_000_000,
           storage_gb: 100,
           api_calls_per_day: 100_000,
         }
       }
    └─ Store in PostgreSQL + Redis cache
    │
    ├─ Create admin user {
         user_id = uuid(),
         tenant_id,
         email = company_email,
         role = "admin",
         mfa_required = true,
       }
    └─ Send password setup link (8-hour expiry)
    │
    ├─ Allocate resources {
         Database: Create tenant_data schema
         Storage: Create s3://bucket/tenant_{id}
         Cache: Create Redis namespace: tenant_{id}:*
         Compute: Register in k8s (namespaces) [Phase 3d]
       }
    │
    ├─ Initialize compliance rules {
         Load governance_api policies for compliance_requirements
         Create tenant-specific audit log (siss-event-log:tenant_id)
         Create compliance baseline metrics
       }
    │
    └─ Send welcome email:
         "Your account is ready!"
         "Admin password reset: [link]"
         "API key: [link to dashboard]"
         "Onboarding docs: [wiki]"

Step 5: Admin Onboarding Session
  Admin logs in (password reset)
    ├─ Require MFA setup (TOTP or WebAuthn)
    └─ Force password change on first login
    │
  Dashboard shows onboarding checklist:
    ├─ [ ] Team members invited (email)
    ├─ [ ] API keys generated
    ├─ [ ] First model deployed
    ├─ [ ] Webhook configured
    └─ [ ] Read: "Quick Start" guide
    │
  Admin completes checklist → graduation from "onboarding" state
```

#### 4.2 Tenant Isolation & Data Boundary

**Component:** `siss-tenant-isolation` (300 LOC Rust + SQL)

```
Tenant Isolation Architecture:

┌──────────────────────────────────────────────────────┐
│                   PostgreSQL Database                 │
├──────────────────────────────────────────────────────┤
│ Shared Tables:                                        │
│  • users (tenant_id, email, roles)                   │
│  • sessions (tenant_id, session_id, user_id)         │
│  • api_keys (tenant_id, key_hash, permissions)       │
│                                                       │
│ Tenant-Scoped Tables (Row-Level Security):           │
│  • tenant_{id}_inferences (tenant_id, model_id, ...) │
│  • tenant_{id}_logs (tenant_id, event_type, ...)     │
│  • tenant_{id}_policies (tenant_id, policy_id, ...) │
│                                                       │
│ RLS Policy:                                           │
│   CREATE POLICY tenant_isolation ON inferences       │
│   USING (tenant_id = current_setting('tenant.id'))   │
└──────────────────────────────────────────────────────┘

Request Processing:

  Incoming Request (with auth token)
    ↓
  siss-auth-orchestrator::validate_jwt()
    ├─ Extract tenant_id from JWT payload
    └─ Extract user_id + roles
    │
  siss-tenant-isolation::set_context()
    ├─ SET LOCAL tenant.id = '<tenant_id>'  [PostgreSQL local variable]
    ├─ Store in request context: request.tenant_id
    └─ Store in request context: request.user_id
    │
  Route Handler executes
    ├─ All DB queries automatically filtered by RLS
    │   Query: SELECT * FROM inferences
    │   Actual: SELECT * FROM inferences WHERE tenant_id = $1
    │
    ├─ API responses tagged with tenant_id (for audit)
    └─ Logs stored in tenant-scoped table
    │
  Response sent to client
    └─ Verify response doesn't contain data from other tenants
       (defensive check, should never happen due to RLS)
```

**Storage Isolation (S3):**

```
S3 Bucket: smaos-tenant-data (encrypted at rest)

Key Prefix: s3://smaos-tenant-data/{tenant_id}/

├─ models/
│  ├─ {model_id}/weights.bin
│  ├─ {model_id}/metadata.json
│  └─ {model_id}/audit_trail.jsonl
│
├─ inferences/
│  ├─ {date}/
│  │  ├─ {inference_id}.json (request + response)
│  │  └─ {inference_id}.log (debug info)
│  └─ index (monthly, for queries)
│
├─ logs/
│  ├─ audit.log (siss-event-log)
│  └─ api_calls.log (access log)
│
└─ backups/
   ├─ {date}T{time}_full.tar.gz (weekly)
   └─ {date}_incremental.tar.gz (daily)

S3 IAM Policy (per tenant):
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject"],
        "Resource": "arn:aws:s3:::smaos-tenant-data/{tenant_id}/*"
      }
    ]
  }
```

**Redis Isolation:**

```
Redis Key Namespace: tenant_{tenant_id}:{key_type}:{key_name}

Examples:
  • tenant_abc123:sessions:sess_xyz
  • tenant_abc123:cache:model_weights_v1
  • tenant_abc123:rate_limit:user_alice:api_calls
  • tenant_abc123:feature_flags:enable_new_ui

Redis RBAC (ACL):
  user default off
  user tenant-abc123 on ~tenant_abc123:* &api-key-abc123 +@all
  user tenant-xyz789 on ~tenant_xyz789:* &api-key-xyz789 +@all
```

#### 4.3 Per-Tenant Quotas & Billing

**Component:** `siss-billing-engine` (250 LOC)

```
Usage Tracking:

Every billable event increments metrics:

  Model Inference:
    event: "model_inference"
    tenant_id: "abc123"
    user_id: "alice@company.com"
    model_id: "gpt-4-finance"
    tokens_used: 2500
    timestamp: "2027-08-31T14:32:15Z"
    ↓
    siss-billing-engine::track_inference()
      ├─ Increment daily_inferences[tenant_id][date]
      ├─ Increment monthly_tokens[tenant_id][month]
      └─ Store event in PostgreSQL (immutable log)
  
  API Call:
    ├─ Increment daily_api_calls[tenant_id]
    └─ Check quota: if daily_api_calls > limit → 429 (Too Many Requests)
  
  Storage:
    ├─ Track object count + total size in s3://smaos-tenant-data/{tenant_id}
    └─ Check quota: if storage > limit → reject uploads (until cleanup)

Quota Enforcement:

  Standard Plan:
    inferences_per_month: 1,000,000
    storage_gb: 100
    api_calls_per_day: 100,000
    concurrent_users: 10
    
  Enterprise Plan:
    inferences_per_month: unlimited
    storage_gb: 1,000
    api_calls_per_day: 1,000,000
    concurrent_users: 1,000
    custom_models: yes
    sso: yes
    sla: 99.99%

Billing Calculation:

  Monthly Invoice:
    Base fee: €500 (Standard) or Custom (Enterprise)
    Overage charges:
      ├─ Inferences: €0.0001 per inference (if > monthly quota)
      ├─ Storage: €0.10 per GB-month (if > included quota)
      └─ API calls: €0.000001 per call (if > daily quota)
    
    Example (Standard Plan, Aug 2027):
      Base: €500
      Inferences: 1,200,000 used, 1,000,000 included
        → 200,000 overage × €0.0001 = €20
      Storage: 150 GB used, 100 GB included
        → 50 GB × €0.10 = €5
      Total: €525
```

#### 4.4 Multi-Tenant Governance & Compliance

**Component:** `siss-tenant-governance` (200 LOC)

```
Per-Tenant Compliance Settings:

  tenant_compliance = {
    tenant_id: "abc123",
    
    required_frameworks: [
      {framework: "EU_AI_ACT", compliant: true, next_audit: "2027-12-01"},
      {framework: "GDPR", compliant: true, dpa_signed: true, dpa_expiry: "2028-08-31"},
      {framework: "SOC_2", compliant: false, target_date: "2027-12-31"},
    ],
    
    data_residency: {
      region: "EU",  # Data must stay in EU
      country: "CZ",  # Prefer Czech Republic
      allowed_processing: ["analytics", "model_training"],
      forbidden_processing: ["cross-border_transfer"],
    },
    
    consent_rules: {
      require_explicit_consent: true,
      consent_storage: "customer_db",  # Not shared with us
      audit_trail: true,
    },
    
    deletion_policy: {
      grace_period_days: 7,
      data_retention_after_deletion: 0,  # Delete immediately after grace period
      backup_retention_days: 30,  # Legal hold for 30 days
    },
    
    audit_requirements: {
      event_log_retention_months: 36,
      log_immutability_required: true,
      encryption_at_rest: "AES-256-GCM",
      encryption_in_transit: "TLS_1_3",
    },
  }

Governance Enforcement:

  When processing inference request for tenant_abc123:
    1. Check data_residency.region → all data in EU
    2. Check consent_rules.require_explicit_consent → user gave consent
    3. Check forbidden_processing → inference doesn't violate this tenant's rules
    4. Log event with data classification (per tenant policy)
    5. Apply encryption (per tenant's encryption_at_rest requirement)

Automated Compliance Checks (daily):
  for each tenant in tenants:
    1. Verify data residency (query_objects_location() matches allowed)
    2. Verify audit log retention (no logs older than retention_months deleted)
    3. Verify encryption (all data at-rest is encrypted)
    4. Flag any violations → alert compliance_officer
    5. Generate compliance_status report (% compliant with settings)
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Onboarding Pipeline**
- Self-service signup (email verification)
- Trial tenant provisioning
- Admin onboarding checklist
- Deliverable: 100 trial customers onboarded

**Phase 3b (Aug-Sep 2027): Tenant Isolation**
- Row-level security (PostgreSQL)
- Storage isolation (S3 prefixes + IAM)
- Redis namespace isolation
- Deliverable: Data access tests (cross-tenant isolation verified)

**Phase 3c (Oct 2027): Billing & Quotas**
- Usage tracking (inferences, storage, API)
- Quota enforcement
- Monthly invoicing
- Deliverable: 10 paying customers, 1 month of billing data

**Phase 3d (Nov-Dec 2027): Governance & Scale**
- Per-tenant compliance settings
- Automated compliance checks
- MMV: Create 100 test tenants → verify isolation
- Deliverable: Multi-tenant infrastructure ready for 1000+ customers

---

## System 5: Performance Optimization

### Design Overview

**Scope:** Database query optimization + caching layers + compression + serialization tuning.

**Current State (Phase 2 End):**
- `l2-knowledge` — pgvector (semantic search)
- `siss-metrics` — Time-series metrics collection
- `siss-memory-plane` — KV cache management

**Gap Analysis:**
- No query optimization analysis
- No distributed cache layer
- No result compression
- No serialization benchmarking
- No query plan profiling

### Architecture Design

#### 5.1 Database Query Optimization

**Component:** `siss-query-optimizer` (200 LOC)

```
Slow Query Capture:

  PostgreSQL Configuration:
    log_min_duration_statement = 100  # Log queries > 100ms
    log_statement = 'mod'  # Log modifications (INSERT, UPDATE, DELETE)
    
  siss-query-optimizer monitors pg_stat_statements:
    SELECT query, calls, mean_time, max_time
    FROM pg_stat_statements
    ORDER BY mean_time DESC
    LIMIT 20

Query Analysis Pipeline:

  Slow Query Detected: "SELECT * FROM inferences WHERE tenant_id = $1" (avg 250ms)
    ↓
  siss-query-optimizer::analyze()
    ├─ EXPLAIN ANALYZE query
    ├─ Check for missing indexes
    ├─ Check for table bloat (VACUUM analysis)
    ├─ Suggest optimization
    └─ Store suggestion in optimization_queue
    
  Suggested Optimization:
    CREATE INDEX idx_inferences_tenant_created
    ON inferences(tenant_id, created_at DESC)
    INCLUDE (model_id, user_id, tokens_used)
    
  Performance Before:
    Planning Time: 0.234 ms
    Execution Time: 248.234 ms (full table scan)
    
  Performance After:
    Planning Time: 0.123 ms
    Execution Time: 12.456 ms (index seek)
    Improvement: 20x faster
    
  Automatic Application:
    siss-query-optimizer::apply_index()
      ├─ LOCK TABLE inferences BRIEFLY  [concurrent safe]
      ├─ CREATE INDEX CONCURRENTLY
      └─ Monitor index bloat (use partial indexes where applicable)
```

**Common Query Optimizations:**

```
Pattern: SELECT COUNT(*) - Slow on large tables

Optimization:
  Use approximate count (faster, trade-off: 10% error margin):
    SELECT reltuples FROM pg_class WHERE relname = 'inferences'
  Or maintain counter table:
    CREATE TABLE inferences_count (tenant_id uuid, count bigint)
    TRIGGER: UPDATE inferences_count ON INSERT/DELETE

Pattern: JOIN across 3+ tables

Optimization:
  Pre-join into materialized view:
    CREATE MATERIALIZED VIEW user_inference_summary AS
    SELECT u.user_id, u.email, i.model_id, COUNT(*) as inference_count
    FROM users u
    LEFT JOIN inferences i ON u.user_id = i.user_id
    GROUP BY u.user_id, i.model_id
    TABLESPACE high_performance_storage
  Refresh daily (off-peak): REFRESH MATERIALIZED VIEW CONCURRENTLY

Pattern: Sorting large result sets

Optimization:
  Use LIMIT + pagination instead of ORDER BY + OFFSET:
    # Slow: SELECT * FROM inferences ORDER BY created_at OFFSET 10000
    # Fast: SELECT * FROM inferences WHERE created_at < $cursor ORDER BY created_at LIMIT 50
  (Cursor-based pagination is 100x faster for large offsets)

Pattern: Vector similarity search (pgvector)

Optimization:
  Use IVFFlat index for semantic search:
    CREATE INDEX idx_embeddings_ivf ON embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
  Trade-off: 99% recall, 10x faster
```

#### 5.2 Multi-Layer Cache Architecture

**Component:** `siss-cache-strategy` (200 LOC)

```
Cache Hierarchy:

┌─────────────────────────────────────────────┐
│ L1: In-Memory Cache (Application)            │
│ • LRU HashMap (Rust: Arc<RwLock<LRU>>)     │
│ • Max 5 GB per pod                          │
│ • TTL: 5 minutes                            │
│ • Hit rate target: 70%                      │
│ • Example: model_weights[model_id]          │
└─────────────────────────────────────────────┘
                    ↓ (miss)
┌─────────────────────────────────────────────┐
│ L2: Distributed Cache (Redis)                │
│ • Redis cluster (3 nodes, replication)      │
│ • Max 256 GB total                          │
│ • TTL: 1 hour                               │
│ • Hit rate target: 80%                      │
│ • Example: inference_results[cache_key]     │
└─────────────────────────────────────────────┘
                    ↓ (miss)
┌─────────────────────────────────────────────┐
│ L3: Database (PostgreSQL)                    │
│ • Primary + read replicas                   │
│ • Max 1 TB (SSD)                            │
│ • TTL: permanent (until deleted by policy)  │
│ • Hit rate target: 100% (source of truth)   │
└─────────────────────────────────────────────┘

Cache Key Strategy:

  Model Weights (immutable):
    Key: model_weights:{model_id}:{version_hash}
    TTL: 1 week (weights don't change)
    Invalidation: None (immutable)
    Example: model_weights:gpt4:sha256_abc123
    
  Inference Results (mutable, user-specific):
    Key: inference_result:{user_id}:{model_id}:{input_hash}
    TTL: 24 hours (results expire daily for freshness)
    Invalidation: When model is updated
    Example: inference_result:user_abc:gpt4:input_hash_xyz
    
  User Profile (semi-mutable):
    Key: user_profile:{user_id}
    TTL: 1 hour (user can change settings)
    Invalidation: On explicit update
    Example: user_profile:alice_123
    
  Compliance Rules (semi-static):
    Key: compliance_rules:{tenant_id}:{framework}
    TTL: 1 day (rules updated infrequently)
    Invalidation: On governance_api update
    Example: compliance_rules:tenant_abc:eu_ai_act

Cache Warmup (startup):
  siss-cache-strategy::warmup()
    ├─ Load top 1000 model weights (by inference count)
    ├─ Populate l9-governance-api policies
    ├─ Load all active user profiles
    └─ Warm up pgvector semantic search cache

Cache Invalidation (on update):
  User profile updated → DELETE user_profile:{user_id}
  Model deployed → DELETE model_weights:* MATCH model_id pattern
  Compliance rules changed → DELETE compliance_rules:*:framework
  
  Invalidation Logic:
    Using Redis WATCH + transaction (atomic):
      WATCH compliance_rules:*
      if compliance_rules changed:
        DISCARD transaction
      else:
        SET new_compliance_rules
        trigger downstream updates
        EXEC
```

#### 5.3 Compression & Serialization

**Component:** `siss-compression-layer` (150 LOC)

```
Compression Strategy:

  Model Weights (static, large):
    Format: msgpack (binary) + zstd compression
    Original: 4.2 GB (gpt-4 weights)
    Compressed: 680 MB (84% reduction)
    Decompression time: 3.2 seconds (on Jetson Thor)
    Stored in: S3 + redis (first 100 MB)
    
  Inference Results (variable size):
    Format: JSON → msgpack → zstd (if > 1 KB)
    Small results (< 1 KB): uncompressed
    Large results (> 1 MB): zstd level 8 (slower compression, better ratio)
    Example: 50 MB inference result → 8 MB compressed (84% reduction)
    
  Event Logs (high volume):
    Format: jsonlines → parquet (columnar) → snappy
    Batch: 10k events per batch
    Compression ratio: 10:1 (1 MB → 100 KB)
    Storage: S3 partitioned by date/tenant
    
  API Requests/Responses (over the wire):
    HTTP Content-Encoding: gzip (default)
    Threshold: compress if > 5 KB
    Level: 6 (balance speed + compression)

Serialization Benchmarks (on Jetson Thor):

  Format       | Serialize Time | Deserialize Time | Size    | Notes
  -------------|----------------|------------------|---------|------------------
  JSON         | 45ms           | 38ms             | 4.2 MB  | Human readable
  MessagePack  | 12ms           | 10ms             | 2.1 MB  | Binary, compact
  Protobuf     | 8ms            | 7ms              | 1.8 MB  | Schema required
  CBOR         | 10ms           | 9ms              | 2.0 MB  | Streaming-friendly
  
  Recommendation: Use MessagePack + zstd for large payloads
                  Use JSON for API responses (human-readable)
                  Use CBOR for agent-to-agent communication (streaming)
```

#### 5.4 Performance Monitoring & Targets

**Component:** `siss-perf-monitor` (150 LOC)

```
Performance SLOs (Service Level Objectives):

  Endpoint: POST /v1/inferences/{model_id}
    Latency (p99): < 500ms
    Throughput: > 1000 inferences/sec
    Cache hit rate: > 80%
    
  Endpoint: GET /v1/compliance/report
    Latency (p99): < 2s
    Throughput: > 100 req/sec
    Cache hit rate: > 90% (compliance rules cached)
    
  Database: PgVector semantic search
    Latency (p99): < 100ms
    Recall: > 99% (accuracy of results)
    
  Cache: Redis
    Latency (p99): < 10ms
    Hit rate: > 80%
    
Monitoring Stack:

  Prometheus (metrics collection):
    • Scrape every 15 seconds
    • Store 15-month retention
    
  Grafana (visualization):
    • Dashboard: "API Latency (p50, p99)"
    • Dashboard: "Cache Hit Rates"
    • Dashboard: "Database Query Performance"
    
  Alerting:
    • If p99_latency > 1s: page on-call
    • If cache_hit_rate < 70%: investigate
    • If error_rate > 0.1%: page immediately
    
  Performance Test (weekly):
    siss-perf-test::load_test()
      ├─ Simulate 1000 concurrent users
      ├─ Run for 30 minutes
      ├─ Verify all SLOs met
      └─ Generate performance report
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Query Optimization**
- Slow query analysis (pg_stat_statements)
- Index recommendations + automated application
- Materialized views for complex JOINs
- Deliverable: 20x average query latency improvement

**Phase 3b (Aug-Sep 2027): Caching Architecture**
- L1 in-memory cache (LRU)
- L2 Redis distributed cache
- Cache warmup + invalidation
- Deliverable: > 80% cache hit rate verified

**Phase 3c (Oct 2027): Compression & Serialization**
- MessagePack + zstd for payloads
- Compression benchmarks (Jetson Thor)
- JSON + gzip for API responses
- Deliverable: 84% reduction in storage size

**Phase 3d (Nov-Dec 2027): Performance Testing**
- Load testing (1000 concurrent users)
- SLO verification (p99 < 500ms)
- Weekly performance tests
- MMV: Run load test → verify SLOs met
- Deliverable: Performance report + monitoring dashboards

---

## System 6: Production Operations & Support

### Design Overview

**Scope:** Monitoring + alerting + log aggregation + runbook documentation.

**Current State (Phase 2 End):**
- `siss-observability` — Distributed tracing infrastructure
- `siss-telemetry-router` — Event routing
- No centralized monitoring stack

**Gap Analysis:**
- No Prometheus + Grafana setup
- No ELK stack (Elasticsearch/Logstash/Kibana)
- No runbook documentation
- No on-call rotation automation
- No incident post-mortems

### Architecture Design

#### 6.1 Monitoring Stack (Prometheus + Grafana)

**Component:** `siss-monitoring-stack` (200 LOC infra-as-code)

```
Prometheus Configuration:

  scrape_configs:
    # Application metrics
    - job_name: 'api-server'
      static_configs:
        - targets: ['localhost:8080']
      scrape_interval: 15s
      
    # PostgreSQL metrics (via postgres_exporter)
    - job_name: 'postgres'
      static_configs:
        - targets: ['localhost:9187']
    
    # Redis metrics (via redis_exporter)
    - job_name: 'redis'
      static_configs:
        - targets: ['localhost:9121']
    
    # Node metrics (host-level: CPU, memory, disk)
    - job_name: 'node'
      static_configs:
        - targets: ['localhost:9100']

Key Metrics Collected:

  Application Metrics:
    • api_request_duration_seconds (histogram)
    • api_request_total (counter)
    • api_errors_total (counter)
    • cache_hit_rate (gauge)
    • model_inference_duration_seconds (histogram)
    • model_tokens_used_total (counter)
    
  Database Metrics:
    • pg_stat_statements (slow queries)
    • pg_database_size_bytes (database size)
    • pg_connections_used (connection count)
    • pg_replication_lag_seconds (replication status)
    
  Infrastructure Metrics:
    • node_cpu_seconds_total (CPU usage)
    • node_memory_bytes_available (RAM available)
    • node_disk_bytes_free (disk space)
    • node_network_transmit_bytes (network traffic)
    
  Custom Compliance Metrics:
    • compliance_score (per framework)
    • security_events_total (threat detection alerts)
    • mfa_success_rate (authentication success)

Grafana Dashboards:

  Dashboard: API Health
    ├─ Graph: Request latency (p50, p99)
    ├─ Graph: Error rate (%)
    ├─ Graph: Throughput (req/sec)
    ├─ Table: Top 10 slowest endpoints
    └─ Status: System overall health
    
  Dashboard: Database Performance
    ├─ Graph: Query latency (p99)
    ├─ Graph: Slow queries (top 5)
    ├─ Graph: Connection pool utilization
    ├─ Graph: Replication lag (seconds)
    └─ Table: Index usage summary
    
  Dashboard: Compliance & Security
    ├─ Graph: Compliance score (per framework)
    ├─ Graph: Security events (timeline)
    ├─ Graph: MFA success rate
    ├─ Table: Active threats
    └─ Graph: Audit log growth
    
  Dashboard: Infrastructure
    ├─ Graph: CPU usage
    ├─ Graph: Memory usage
    ├─ Graph: Disk space
    ├─ Graph: Network traffic
    └─ Status: Pod health (Kubernetes)
```

#### 6.2 Log Aggregation (ELK Stack)

**Component:** `siss-logging-stack` (250 LOC)

```
ELK Stack Architecture:

  Elasticsearch:
    • 3-node cluster (replication)
    • Index per day (for easy rotation): logs-2027-08-31
    • 30-day retention (compliance: audit logs 36 months)
    • Full-text search capability
    • Total capacity: 100 GB (30 days × ~3 GB/day)
    
  Logstash:
    • Input: Filebeat agents (one per pod/host)
    • Filter: Parse JSON, extract fields, tag by service
    • Output: Elasticsearch + S3 archive (for long-term retention)
    
  Kibana:
    • Discover tab: search/filter logs
    • Dashboard: visual log summaries
    • Alerts: trigger on log patterns

Log Sources:

  1. Application logs (JSON format):
     timestamp, level, service, message, user_id, tenant_id, trace_id, ...
     Example:
       {
         "timestamp": "2027-08-31T14:32:15.234Z",
         "level": "INFO",
         "service": "api-server",
         "message": "User authenticated",
         "user_id": "alice_123",
         "tenant_id": "tenant_abc",
         "trace_id": "0x7f3a...",
         "duration_ms": 45,
       }
  
  2. Access logs (Apache format):
     timestamp, ip, method, endpoint, status, size, duration_ms
  
  3. Security logs (from siss-event-log):
     All events: auth, authorization, policy violations
  
  4. Audit logs (immutable, compliance):
     All system changes, signed with KMS

Kibana Queries (examples):

  # Find all errors in last hour
  level:ERROR AND timestamp:> now-1h

  # Find all API errors for tenant_abc
  service:api-server AND tenant_id:tenant_abc AND level:ERROR

  # Find slow API calls (> 1s)
  duration_ms: [1000 TO *] AND service:api-server

  # Find failed authentication attempts
  message:authentication AND status:fail AND timestamp:> now-24h

  # Find data exfiltration attempts
  message:data_exfiltration OR anomaly_type:data_exfiltration
```

#### 6.3 Alert Management

**Component:** `siss-alerting-engine` (200 LOC)

```
Alert Configuration (Prometheus AlertManager):

  Group: API Health
    Alert: ApiLatencyHigh
      condition: p99_latency > 1s for 5 minutes
      severity: CRITICAL
      action: Page on-call engineer
      
    Alert: ErrorRateHigh
      condition: error_rate > 1% for 5 minutes
      severity: CRITICAL
      action: Page on-call engineer
      
    Alert: ThroughputLow
      condition: throughput < 100 req/sec for 10 minutes
      severity: WARNING
      action: Send to Slack #incidents
  
  Group: Database Health
    Alert: DatabaseConnectionPoolFull
      condition: connections_used / connections_max > 0.9 for 2 minutes
      severity: CRITICAL
      action: Page on-call DBA
      
    Alert: ReplicationLagHigh
      condition: replication_lag_seconds > 30 for 5 minutes
      severity: HIGH
      action: Page on-call DBA
      
    Alert: DiskSpaceRunningOut
      condition: disk_percent_used > 90% for 1 hour
      severity: WARNING
      action: Send to Slack #infrastructure
  
  Group: Compliance & Security
    Alert: ComplianceScoreDrop
      condition: compliance_score drop > 5% from previous day
      severity: HIGH
      action: Notify compliance_officer@smaos.sn
      
    Alert: MaliciousActivityDetected
      condition: anomaly_score > 0.95 for any event
      severity: CRITICAL
      action: Page SOC team, block user

Alert Routing (AlertManager):

  PagerDuty:
    • CRITICAL severity alerts
    • Incidents requiring immediate response
    • Escalation: 5 min → on-call, 15 min → manager
    
  Slack:
    • HIGH severity alerts
    • Non-critical warnings
    • Channel: #incidents (real-time updates)
    
  Email:
    • LOW severity alerts
    • Informational alerts
    • Recipient: engineering@smaos.sn (daily digest)
    
  Custom Webhooks:
    • Incident creation (incident.io)
    • Ticketing (Jira)
    • Communication (Slack → email fallback)
```

#### 6.4 Runbook Documentation

**Component:** `siss-runbooks` (documentation, not code)

```
Runbook: API Latency High (p99 > 1 second)

Symptom:
  Prometheus alert "ApiLatencyHigh" fired
  Dashboard shows p99 latency > 1s for 5+ minutes
  
Diagnosis:
  1. Check Grafana dashboard "API Health"
     • Is it specific endpoint or all endpoints?
     • Is it specific client or all clients?
  
  2. Query slow queries:
     SELECT query, mean_time, max_time
     FROM pg_stat_statements
     ORDER BY mean_time DESC
     LIMIT 5;
  
  3. Check Redis cache hit rate:
     redis-cli INFO stats | grep keyspace_hits
     (target: > 80%)
  
  4. Check database replication lag:
     SELECT now() - pg_last_xact_replay_timestamp() as lag;
     (target: < 100ms)
  
  5. Check Kibana for errors:
     level:ERROR AND service:api-server AND timestamp:> now-5m
     (are errors causing slowdown?)

Mitigation (immediate, 2-5 minutes):
  Option A: If cache hit rate is low (< 60%)
    1. Clear Redis cache (data will be re-populated on next request)
       redis-cli FLUSHDB ASYNC
    2. Monitor: check if hit rate improves
    3. Investigate: why are we getting cache misses?
  
  Option B: If database is slow
    1. Check for long-running queries:
       SELECT * FROM pg_stat_activity WHERE state != 'idle';
    2. If found: kill slow query (use pg_terminate_backend)
       SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE ...;
    3. Monitor: check if latency drops
  
  Option C: If specific endpoint is slow
    1. Restart pod for that endpoint
       kubectl delete pod <api-pod-name>
       (Kubernetes auto-restarts it)
    2. Monitor: check if latency improves
    3. Investigate root cause
  
  Option D: If all endpoints slow + no clear cause
    1. Scale up API pods:
       kubectl scale deployment api-server --replicas=5
    2. Monitor: latency should drop as load spreads
    3. Investigate root cause while scaled up

Root Cause Analysis (post-incident, 10-30 minutes):
  1. Export metrics from Prometheus (1 hour window)
  2. Export logs from Kibana (error + warning level)
  3. Check git log (any deployments in last hour?)
  4. Review database performance (any bloat/fragmentation?)
  5. Check resource usage (any pods out of memory?)
  
Prevention (future):
  • Add index if slow query is missing one
  • Increase cache TTL if cache misses are high
  • Set resource limits on pods (prevent OOM)
  • Deploy gradual rollouts (catch regressions early)

Success Criteria:
  ✓ Alert fires immediately when p99 > 1s
  ✓ On-call engineer acknowledges within 2 min
  ✓ Mitigation started within 5 min
  ✓ Latency returns to < 500ms p99
  ✓ Root cause documented in incident ticket
```

**Other Runbooks (summary):**

| Runbook | Symptom | Mitigation | Prevention |
|---------|---------|-----------|-----------|
| DB Replication Lag High | replication_lag > 30s | Check network, restart replica | Monitor replication health daily |
| Disk Space Full | disk_used > 95% | Delete old logs, archive to S3 | Automate log rotation |
| Security Event Detected | anomaly_score > 0.95 | Revoke user sessions, investigate | Review threat model quarterly |
| Compliance Score Drop | score decrease > 5% | Run gap detection, fix violations | Continuous compliance monitoring |

#### 6.5 Incident Management

**Component:** `siss-incident-management` (150 LOC)

```
Incident Workflow:

1. Alert fires (Prometheus)
   ↓
2. PagerDuty notifies on-call engineer
   ↓
3. On-call opens incident dashboard
   → Shows: alert details, recent changes, historical context
   ↓
4. On-call acknowledges incident
   → Automatic Slack notification: "incident acknowledged"
   ↓
5. Diagnosis (using runbook)
   → Identify root cause + severity
   ↓
6. Mitigation
   → Implement fix (scale up, kill process, etc.)
   → Monitor: verify fix works
   ↓
7. Communication
   → Update status page: "Investigating API latency issue"
   → Notify affected customers (if SLA impacted)
   ↓
8. Close incident
   → If latency returns to normal: close
   → If still investigating: escalate (call manager)
   ↓
9. Post-Mortem (within 48 hours)
   → Timeline of events + actions taken
   → Root cause analysis
   → Action items to prevent recurrence
   → Share findings with team

Incident Severity Levels:

  SEV-1 (Critical):
    • Complete service outage
    • Data corruption / loss
    • Security breach
    • SLA violated (99.99% uptime)
    Response time: < 5 minutes
    Escalation: CTO + on-call team
    
  SEV-2 (High):
    • Degraded performance (> 10% error rate)
    • Single region affected
    • Feature partially unavailable
    Response time: < 15 minutes
    Escalation: on-call team
    
  SEV-3 (Medium):
    • Minor feature issue
    • No customer impact
    • Expected to resolve within 1 hour
    Response time: < 1 hour
    Escalation: engineering team

Post-Mortem Template:

  Incident: API Latency High (p99 > 1s on Aug 31)
  Duration: 2027-08-31 14:32 - 14:47 (15 minutes)
  Impact: 0.2% of requests affected, 5 customers impacted
  Severity: SEV-2 (high)
  
  Timeline:
    14:32 - Alert fires (p99 > 1s)
    14:33 - On-call acknowledges
    14:35 - Diagnosed: missing database index
    14:40 - Mitigation: created index CONCURRENTLY
    14:45 - Latency dropped to < 200ms
    14:47 - Incident closed
  
  Root Cause:
    Query "SELECT * FROM inferences WHERE created_at > $1"
    was full table scan (no index on created_at).
    New feature (added yesterday) started using this query.
  
  Action Items:
    • Add query optimizer to CI/CD (catch unindexed queries)
    • Review all queries added in last 24h for index coverage
    • Update onboarding: require EXPLAIN ANALYZE for queries
    
  Preventive Measures:
    • Automated index recommendations on query analysis
    • Performance testing in CI (detect query regressions)
    • Code review: require EXPLAIN output for new queries
```

### Timeline & Deliverables

**Phase 3a (Jun-Jul 2027): Monitoring Stack**
- Prometheus configuration
- Grafana dashboards (API, database, compliance)
- Alert rules (Prometheus AlertManager)
- Deliverable: Full monitoring coverage (all services)

**Phase 3b (Aug-Sep 2027): Log Aggregation**
- ELK stack setup (Elasticsearch, Logstash, Kibana)
- Log source integration (app, access, security, audit)
- Kibana queries + dashboards
- Deliverable: 30-day searchable log retention

**Phase 3c (Oct 2027): Alert Management**
- PagerDuty + Slack integration
- Alert routing (severity-based)
- Alert suppression (prevent alert fatigue)
- Deliverable: Alert response SLA < 5 minutes (CRITICAL)

**Phase 3d (Nov-Dec 2027): Runbooks & Post-Mortems**
- Runbook documentation (10+ scenarios)
- Incident post-mortem template
- On-call rotation automation
- MMV: Simulate incident → verify runbook works → close incident
- Deliverable: Operations team ready for 24/7 support

---

## Integration Architecture

### Cross-System Data Flows

```
┌─────────────────────────────────────────────────────────────────┐
│                       Customer Request Flow                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Customer visits https://smaos.sn (onboarding dashboard)     │
│     → System 4 (Onboarding): Customer signup → tenant created   │
│                                                                  │
│  2. Customer logs in                                             │
│     → System 1 (Auth): SAML/OAuth → MFA challenge → JWT token   │
│                                                                  │
│  3. Customer deploys model + sets compliance requirements       │
│     → System 2 (Compliance): Create audit trail, initialize     │
│                               compliance baseline                │
│                                                                  │
│  4. Customer runs inference                                      │
│     → System 5 (Perf): Query cache → if miss, execute model     │
│     → System 3 (Threat): Log event, analyze for anomalies       │
│     → System 6 (Ops): Record metrics (latency, tokens used)     │
│                                                                  │
│  5. Monthly: Auto-generate compliance report                    │
│     → System 2 (Compliance): Collect events, calculate score,   │
│                              generate PDF + KMS signature       │
│     → System 6 (Ops): Alert if score drops                      │
│                                                                  │
│  6. Incident detected (e.g., suspicious auth)                   │
│     → System 3 (Threat): Flag anomaly, suggest mitigation       │
│     → System 1 (Auth): Revoke sessions, force MFA re-verify     │
│     → System 6 (Ops): PagerDuty alert, incident investigation   │
│                                                                  │
│  7. Annual audit                                                │
│     → System 6 (Ops): Export 12 months of signed audit logs     │
│     → System 2 (Compliance): Generate compliance bundle (PDFs)  │
│     → System 1 (Auth): Verify all decisions were properly auth  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### API Boundaries

```
System 1 (Auth) exposes:
  POST /auth/saml/acs (IdP assertion)
  POST /auth/token (OAuth token exchange)
  GET  /.well-known/jwks.json (public keys)
  POST /auth/mfa/verify (TOTP)
  → Used by: System 4 (onboarding), Systems 2-6 (request validation)

System 2 (Compliance) exposes:
  GET  /compliance/report/{tenant_id} (latest report)
  GET  /compliance/score (current compliance %)
  GET  /compliance/gaps (open gaps)
  POST /compliance/collect (hook: collect new event)
  → Used by: System 3 (anomaly context), System 6 (alerts)

System 3 (Threat) exposes:
  POST /threat/analyze (analyze event for anomalies)
  GET  /threat/incidents (list incidents)
  POST /threat/forensics (build incident timeline)
  → Used by: System 1 (auth), System 6 (ops)

System 4 (Onboarding) exposes:
  POST /onboarding/signup (customer registration)
  GET  /onboarding/status (signup progress)
  POST /onboarding/provision (tenant creation)
  → Used by: External (customer-facing)

System 5 (Perf) exposes:
  GET  /cache/stats (hit rate, size)
  POST /cache/warm (cache warmup)
  → Used by: System 6 (ops), others (implicit)

System 6 (Ops) exposes:
  GET  /metrics/api (Prometheus endpoint)
  GET  /logs/search (Kibana queries)
  GET  /alerts (current active alerts)
  POST /incident/{incident_id}/resolve (close incident)
  → Used by: External (dashboards, on-call)
```

---

## Success Metrics & SLOs

### Phase 3 Completion Criteria

| System | Metric | Target | Measurement |
|--------|--------|--------|-------------|
| System 1: Auth | SAML 2.0 certification | PASS | Third-party audit report |
| | OAuth 2.0 token issuance | < 50ms p99 | Prometheus metrics |
| | MFA enrollment rate | > 90% (admins) | PostgreSQL query |
| System 2: Compliance | Report generation time | < 30s | Timed test run |
| | Compliance score accuracy | > 99% | Auditor verification |
| | Multi-framework mapping | 100% coverage | Manual audit |
| System 3: Threat | Anomaly detection accuracy | Precision 96%, Recall 91% | Test set evaluation |
| | Incident response time | < 5 min (CRITICAL) | Post-mortem analysis |
| | Forensics timeline generation | < 2s per incident | Performance test |
| System 4: Onboarding | Customer signup → tenant | < 10 min | End-to-end test |
| | Multi-tenant isolation | 100% data separation | Security test |
| | Billing accuracy | > 99.9% | Reconciliation audit |
| System 5: Perf | API latency (p99) | < 500ms | Prometheus metrics |
| | Cache hit rate | > 80% | Redis stats |
| | Query execution | < 100ms (pgvector) | Database metrics |
| System 6: Ops | Alert response time | < 5 min | PagerDuty logs |
| | Log search latency | < 1s (Kibana) | Performance test |
| | Runbook accuracy | 100% (no deviations) | Post-mortem review |

### Production SLA Targets

```
Service Level Agreement (SLA):

  Availability:
    Target: 99.99% (4 nines)
    = 52 minutes downtime per year
    = 4 minutes downtime per month
    
  Latency:
    API endpoints: p99 < 500ms
    Database queries: p99 < 100ms
    Cache hits: p99 < 10ms
    
  Compliance:
    Compliance reports: 100% accuracy
    Audit trail: 100% completeness (no lost events)
    Regulatory deadlines: 100% met
    
  Security:
    Mean Time to Detect (MTTD): < 5 minutes
    Mean Time to Respond (MTTR): < 15 minutes
    False positive rate: < 0.1%
    
  Support:
    CRITICAL incident: response < 5 min, resolution target < 2h
    HIGH incident: response < 15 min, resolution target < 8h
    MEDIUM incident: response < 1h, resolution target < 24h
```

---

## Timeline & Sequencing

### Phase 3a: Foundation (Jun-Jul 2027)

- System 1: SAML 2.0 + OAuth 2.0 foundation
- System 2: Compliance data collection
- System 4: Self-service onboarding
- System 5: Query optimization analysis
- System 6: Prometheus + Grafana setup

**Deliverable:** All 5 systems foundation layers, unit tests passing

### Phase 3b: Core Features (Aug-Sep 2027)

- System 1: MFA (TOTP, WebAuthn) + session management
- System 2: Compliance analyzer + report generator
- System 3: Anomaly detection model + real-time scoring
- System 4: Tenant isolation (database + storage + Redis)
- System 5: Caching architecture (L1/L2/L3)
- System 6: Log aggregation (ELK stack)

**Deliverable:** All systems integration tested, MMV 50% complete

### Phase 3c: Advanced Features (Oct 2027)

- System 1: Token revocation + device trust
- System 2: Multi-framework mapping + gap detection
- System 3: Intrusion detection + forensic investigation
- System 4: Billing engine + quota enforcement
- System 5: Compression + serialization tuning
- System 6: Alert management + on-call routing

**Deliverable:** All systems feature complete, performance testing begins

### Phase 3d: Production Readiness (Nov-Dec 2027)

- System 1: Security audit + hardening
- System 2: Compliance audit + cross-framework validation
- System 3: Incident response automation + playbook testing
- System 4: Load testing (1000+ tenants)
- System 5: Performance SLA verification
- System 6: Runbook documentation + incident drills

**Deliverable:** All systems production-ready, MMV 100% complete, operations team trained

---

## Cost Estimate (€1.8M Total)

### Engineering Resources

```
Phase 3a-3d (12 months):

Team:
  • 2x Senior Engineers (systems design + architecture)
  • 2x Full-Stack Engineers (implementation)
  • 1x Security Engineer (threat modeling, audits)
  • 1x DevOps Engineer (infrastructure, monitoring)
  • 1x QA Engineer (testing + MMV protocol)
  • 1x Product Manager (requirements + prioritization)

Cost (loaded):
  6 FTE × €150k/year = €900k
  (includes: salary, benefits, taxes, overhead)
```

### Infrastructure & Tools

```
Development:
  • AWS/GCP compute (dev + test): €5k/month × 12 = €60k
  • Datadog/New Relic (observability tools): €2k/month × 12 = €24k
  • Third-party services (Okta, Auth0, etc. for testing): €5k/month × 12 = €60k
  • Jetson Thor hardware (3 units for testing): €15k × 3 = €45k

Production:
  • PostgreSQL cluster (3 nodes, HA): €20k/month × 12 = €240k
  • Redis cluster (3 nodes, high-memory): €10k/month × 12 = €120k
  • Kubernetes cluster (20 nodes, GPU): €15k/month × 12 = €180k
  • S3 storage (compliance data, 10 TB): €2k/month × 12 = €24k
  • ELK stack (Elasticsearch, Kibana, Logstash): €5k/month × 12 = €60k
  • Monitoring (Prometheus, Grafana, AlertManager): €1k/month × 12 = €12k
  • CDN (Cloudflare, if needed): €2k/month × 12 = €24k

Total Infrastructure: €769k
```

### Third-Party Services & Licenses

```
  • SAML 2.0 IdP (Okta, Azure AD): €100/month × 12 = €1.2k
  • Certificate authority (SSL/TLS, code signing): €5k/year
  • Threat intelligence feeds (IP reputation, malware): €10k/year
  • Security audit (third-party): €50k (one-time)
  • Compliance audit (EU AI Act + SOC 2): €100k (one-time)
  • Legal review (contracts, terms): €30k (one-time)
  • PagerDuty (incident management): €2k/month × 12 = €24k
  • Slack (communication): €0.5k/month × 12 = €6k

Total Services: €256.2k
```

### Contingency (15%)

```
Total without contingency: €900k + €769k + €256.2k = €1,925.2k
Contingency (15%): €288.8k
Total with contingency: €2,214k

However, Phase 1 + Phase 2 budgets may already cover some infrastructure.
**Adjusted estimate (assuming existing infrastructure reuse): €1.8M**
```

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| SAML 2.0 IdP integration complexity | Medium | High | Use tested libraries (pysaml2), early PoC |
| Multi-tenant isolation bugs | Medium | Critical | Comprehensive security testing, code review |
| Anomaly detection false positives | High | Medium | Conservative thresholds, human-in-the-loop |
| Performance SLA miss (p99 > 500ms) | Medium | High | Early load testing, caching optimization |
| Compliance audit failures | Low | Critical | Engage auditors early, iterative validation |
| On-call team burnout | Medium | High | Automated runbooks, alerting tuning |

---

## Success Indicators (May 31, 2028)

- ✅ All 6 systems production-deployed and live
- ✅ 1000+ paying customers using platform
- ✅ 99.99% uptime SLA maintained (52-minute downtime/year)
- ✅ SAML 2.0 + OAuth 2.0 certification (third-party)
- ✅ Compliance reports auto-generated (all 3 frameworks)
- ✅ Threat detection model: 96% precision, 91% recall
- ✅ API latency p99 < 500ms (99% of requests)
- ✅ 24/7 on-call operations (CRITICAL response < 5 min)
- ✅ Annual compliance audit passed (zero critical findings)
- ✅ Cost-per-deployment reduced to €150/month

---

## Appendix: Component Summary

| System | Component | LOC | Status | Testing |
|--------|-----------|-----|--------|---------|
| 1 | siss-saml-provider | 300 | Design | Unit + Integration |
| 1 | siss-oauth-server | 400 | Design | Unit + Integration |
| 1 | siss-mfa-orchestrator | 250 | Design | Unit + Integration |
| 1 | siss-session-manager | 200 | Design | Unit + Integration |
| 2 | siss-compliance-collector | 350 | Design | Unit + Integration |
| 2 | siss-compliance-analyzer | 300 | Design | Unit + Integration |
| 2 | siss-report-generator | 250 | Design | Unit + Integration |
| 2 | siss-framework-mapper | 200 | Design | Unit + Integration |
| 3 | siss-anomaly-detector | 400+300 | Design | Unit + Integration |
| 3 | siss-intrusion-detector | 250 | Design | Unit + Integration |
| 3 | siss-forensics-engine | 300 | Design | Unit + Integration |
| 4 | siss-onboarding-service | 350 | Design | Unit + Integration |
| 4 | siss-tenant-isolation | 300 | Design | Security testing |
| 4 | siss-billing-engine | 250 | Design | Unit + Integration |
| 4 | siss-tenant-governance | 200 | Design | Unit + Integration |
| 5 | siss-query-optimizer | 200 | Design | Performance testing |
| 5 | siss-cache-strategy | 200 | Design | Unit + Integration |
| 5 | siss-compression-layer | 150 | Design | Performance testing |
| 5 | siss-perf-monitor | 150 | Design | Integration testing |
| 6 | siss-monitoring-stack | 200 | Design | Infrastructure testing |
| 6 | siss-logging-stack | 250 | Design | Integration testing |
| 6 | siss-alerting-engine | 200 | Design | Unit + Integration |
| 6 | siss-incident-management | 150 | Design | Simulation testing |
| | | **~6,500** | | **Full Coverage** |

---

## Document Sign-Off

**Prepared by:** Architecture Team  
**Date:** Sep 5, 2026  
**Review Status:** READY FOR IMPLEMENTATION PLANNING  
**Next Phase:** Phase 3 Implementation Roadmap (late Oct 2026)  

---

**End of Design Document**

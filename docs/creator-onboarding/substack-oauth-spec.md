# Substack OAuth Integration Spec

**Target Launch:** August 15, 2026  
**Scope:** Creator authentication & publication sync  
**Status:** Design (pre-implementation)

---

## 1. Overview

Creators connect their Substack publications to AXIOM via OAuth 2.0 authorization. The flow grants AXIOM temporary access to read creator profiles, publication metadata, and subscriber counts. All tokens are encrypted and revocable by the creator at any time.

**Key Promise:** "We'll never post on your behalf. We only read your audience metadata."

---

## 2. OAuth 2.0 Authorization Flow

### 2.1 Flow Sequence

```
┌─────────────┐
│  Creator    │
│  Dashboard  │
└──────┬──────┘
       │ 1. Click "Connect Substack"
       ▼
┌─────────────────────────────────────────┐
│ AXIOM Creator OAuth Handler             │
│ /api/v1/creator/oauth/substack/start    │
│ • Generate random state token (32 bytes)│
│ • Store state in Redis (5 min TTL)      │
│ • Redirect to Substack auth endpoint    │
└────────────────────┬────────────────────┘
                     │ 2. Redirect with state
                     ▼
              ┌─────────────┐
              │  Substack   │
              │  OAuth Page │
              └──────┬──────┘
                     │ 3. Creator grants permission
                     ▼
┌─────────────────────────────────────────┐
│ AXIOM OAuth Callback                    │
│ /api/v1/creator/oauth/substack/callback │
│ • Verify state token                    │
│ • Exchange auth code for access token   │
│ • Fetch creator profile data            │
│ • Encrypt token → encrypted keychain    │
│ • Store session in Redis (30-day TTL)   │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ Creator Profile Synced   │
│ (dashboard redirect)     │
└──────────────────────────┘
```

### 2.2 Request Parameters

**Authorization Endpoint:** `https://substack.com/oauth/authorize`

```
GET /oauth/authorize?
  client_id=<AXIOM_CLIENT_ID>
  &redirect_uri=https://creator.axiom.co/api/v1/creator/oauth/substack/callback
  &response_type=code
  &scope=publications.read%20posts.read%20subscribers.read
  &state=<RANDOM_32_BYTE_HEX>
```

**Token Endpoint:** `https://substack.com/api/v1/oauth/token`

```
POST /api/v1/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<AUTH_CODE>
&client_id=<AXIOM_CLIENT_ID>
&client_secret=<AXIOM_CLIENT_SECRET>
&redirect_uri=https://creator.axiom.co/api/v1/creator/oauth/substack/callback
```

---

## 3. Scopes & Permissions

| Scope | Permission | Usage |
|-------|-----------|-------|
| `publications.read` | Read publication metadata | Fetch publication name, description, founding date |
| `posts.read` | Read published post titles & dates | Calculate audience engagement (posts/month) |
| `subscribers.read` | Read paid & free subscriber counts | Display in creator dashboard; estimate revenue potential |

**NOT REQUESTED:**
- `posts.write` — We never post on creator's behalf
- `subscribers.modify` — We never add/remove/email subscribers
- `billing.read` — We don't access Substack revenue data

---

## 4. Token Storage & Encryption

### 4.1 Encrypted Keychain Storage (Persistent)

Each creator's access token is encrypted at rest and stored in an encrypted keychain:

```
Creator ID (UUID) → Encrypted AES-256-GCM {
  access_token: "sub_...",
  token_type: "Bearer",
  expires_at: "2026-08-15T23:59:59Z",
  refresh_token: "sub_refresh_...",
  scope: "publications.read posts.read subscribers.read",
  created_at: "2026-06-04T12:00:00Z"
}
```

**Encryption Details:**
- Algorithm: AES-256-GCM (NIST approved)
- Key derivation: PBKDF2 (100,000 iterations)
- Key storage: AWS Secrets Manager (envelope encryption)
- Nonce: 12-byte random per token
- Auth tag: Included in ciphertext

**Access Control:**
- Only the creator's own creator service can decrypt
- Decryption requires: creator_id + service signing key
- Audit log: Every decryption is logged to behavioral firewall

### 4.2 Session Token Storage (Temporary, Redis)

After successful OAuth, a short-lived session is created:

```
Session ID (JWT) → Redis {
  creator_id: "uuid-...",
  publication_id: "pub-...",
  access_level: "read:publications",
  expires_at: 2026-06-05T12:00:00Z (30 days)
}
```

**Redis Configuration:**
- Key: `creator_session:{session_id}`
- TTL: 30 days (auto-expire)
- Backup: Enabled (RDS snapshots)
- Cluster: Multi-AZ with read replicas

---

## 5. Token Refresh & Expiration

### 5.1 Refresh Token Lifecycle

**Substack token expiry:** 90 days (per Substack API contract)

```
Token Expiry Flow:
├─ Day 45: Silent refresh attempt in background
│  └─ On success: Update encrypted keychain, reset TTL
│  └─ On failure: Flag creator_id for manual reconnection
├─ Day 88: Creator receives email: "Reconnect Substack?"
└─ Day 90: Token expires; disconnect in dashboard
```

**Refresh Mechanism:**
- Cron job runs daily at 02:00 UTC
- Queries all creators with tokens expiring in 45 days
- Attempts refresh via Substack `refresh_token` endpoint
- Writes result to behavioral firewall audit log

### 5.2 Validation & Error Handling

**On token validation failure:**
1. Attempt refresh (if refresh_token exists)
2. If refresh fails: Mark creator as "requires_reconnection"
3. Trigger automated email: "Your Substack connection expired"
4. Creator clicks link → OAuth flow restarts

---

## 6. Revocation Flow (Creator Disconnect)

**User Journey:** Creator Dashboard → Settings → Connected Accounts → "Disconnect Substack"

### 6.1 Revocation Steps

```
1. Creator clicks "Disconnect" button
   ↓
2. POST /api/v1/creator/oauth/substack/revoke
   {
     "creator_id": "uuid-...",
     "reason": "user_initiated" | "token_expired" | "account_deleted"
   }
   ↓
3. Backend:
   ├─ Delete encrypted token from keychain
   ├─ Revoke session token (remove from Redis)
   ├─ Call Substack revocation endpoint (optional, for cleanliness)
   ├─ Log to behavioral firewall: creator_oauth_revoked
   └─ Clear any cached publication/subscriber data older than 30 days
   ↓
4. Return 204 No Content
   ↓
5. Frontend shows: "Substack disconnected"
   Creator must reconnect to use creator dashboard features
```

### 6.2 Data Cleanup on Revocation

| Data | Action | Retention |
|------|--------|-----------|
| Access token | Delete immediately | — |
| Refresh token | Delete immediately | — |
| Session token | Delete immediately | — |
| Cached profile metadata | Keep (anonymized) | 30 days, then delete |
| Subscriber counts (historical) | Keep for analytics | 90 days, then delete |
| Audit logs (who saw what when) | Keep (immutable) | 7 years (regulatory) |

---

## 7. Test Cases & Mock API Responses

### 7.1 Success Scenario: Happy Path

**Mock Substack API Response — POST /api/v1/oauth/token**

```json
{
  "access_token": "sub_7f9a2c1e5b3d9e8c2a4f7b5d9e1c3a5f",
  "token_type": "Bearer",
  "expires_in": 7776000,
  "refresh_token": "sub_refresh_9e2a1f5c7b3e8d4a6c2f9e1a3b5d7f9c",
  "scope": "publications.read posts.read subscribers.read"
}
```

**Mock Substack API Response — GET /api/v1/publications (user's)**

```json
{
  "data": [
    {
      "id": "pub_abc123",
      "name": "The Sovereign Stack",
      "description": "AI governance for creators",
      "founding_date": "2025-03-15",
      "subdomain": "sovereign-stack",
      "subscriber_count": {
        "free": 4250,
        "paid": 312
      },
      "post_count": 47,
      "latest_post_date": "2026-06-04"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 1
  }
}
```

### 7.2 Error Scenario: Invalid State Token

**Request:**

```
GET /api/v1/creator/oauth/substack/callback?
  code=auth_xyz
  &state=invalid_state_token
```

**Expected Response:**

```json
{
  "error": "invalid_state_token",
  "error_description": "State token not found or expired. Please restart OAuth flow.",
  "redirect_url": "/creator/settings/integrations?error=oauth_state_mismatch"
}
HTTP 400
```

### 7.3 Error Scenario: Token Refresh Failure

**Substack Response:**

```json
{
  "error": "invalid_grant",
  "error_description": "Refresh token has expired"
}
```

**AXIOM Action:**
1. Log to behavioral firewall: `creator_token_refresh_failed`
2. Mark creator as `requires_reconnection = true`
3. Queue email: "Your Substack connection needs renewal"
4. Display banner in dashboard: "⚠️ Reconnect your Substack account"

### 7.4 Error Scenario: Network Timeout

**Scenario:** Substack OAuth endpoint is down (5+ second latency)

**Fallback:**
1. After 5 seconds: Return HTTP 504 Gateway Timeout
2. Frontend shows: "Substack is temporarily unavailable. Try again in a few minutes."
3. Log to behavioral firewall: `external_service_timeout`
4. Alert: Ops team gets PagerDuty alert if >5 timeouts in 1 hour

---

## 8. QA Test Matrix

| Test Case | Input | Expected Behavior | Pass Criteria |
|-----------|-------|-------------------|---------------|
| **T1: OAuth success** | Valid Substack user | Creator profile loaded, token encrypted, session created | Dashboard shows publication name + subscriber counts |
| **T2: Invalid state** | Tampered state param | Error page, no token stored | Error message clear, user can restart OAuth |
| **T3: Token expiry** | Token with 90-day TTL | Silent refresh at day 45 | New token valid, no user action needed |
| **T4: Refresh failure** | Expired refresh token | User prompted to reconnect | Email sent, dashboard shows reconnect prompt |
| **T5: Revocation** | User clicks disconnect | All tokens deleted, session cleared | Dashboard no longer shows Substack data |
| **T6: Network timeout** | Substack API unreachable | Graceful fallback, user sees error | User can retry without data corruption |
| **T7: Scope validation** | Substack grants fewer scopes | Creator warned, limited features | Dialog: "We need access to subscriber counts" |
| **T8: Multi-publication** | Creator with 3 publications | All publications listed in dashboard | Dropdown selector shows all 3 pubs |

---

## 9. Security Considerations

### 9.1 CSRF Protection

- All OAuth redirects include state parameter (IETF RFC 6749 §10.12)
- State tokens are 32 bytes of cryptographically secure random data
- State tokens expire after 5 minutes (in Redis)
- Mismatch → reject with 400 Bad Request

### 9.2 Token Leakage Prevention

- Access tokens never logged to stdout/stderr
- Encrypted keychain uses HSM (AWS CloudHSM if available)
- Token in HTTP headers: `Authorization: Bearer sub_...`
- HTTPS-only; no HTTP fallback

### 9.3 XSS Mitigation

- OAuth callback parameter validation: Base64 decode only, no eval
- Session token stored in secure, HTTP-only cookie (not localStorage)
- CSP header: `script-src 'self'` (no inline scripts)

### 9.4 Man-in-the-Middle (MITM) Prevention

- Enforce HTTPS for all OAuth endpoints
- HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- TLS 1.3+ only
- Certificate pinning on Substack endpoint (if using SDK)

### 9.5 Rate Limiting

- OAuth initiation: 10 requests/IP/hour
- Token refresh: 1 request/creator/hour (exponential backoff if failure)
- Callback endpoint: 100 requests/minute/IP (detect brute force)

---

## 10. Monitoring & Alerts

### 10.1 Metrics

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| `oauth_completion_rate` | <85% daily | Investigate form abandonment |
| `token_refresh_failure_rate` | >5% | Check Substack API status |
| `revocation_rate` | >10% weekly | Investigate user dissatisfaction |
| `oauth_callback_errors_5xx` | >2% | Page ops, investigate backend |

### 10.2 Logging to Behavioral Firewall

Every OAuth event is logged with:

```rust
AuditEvent {
  event_type: "creator_oauth_substack_start" | "creator_oauth_substack_token_received" 
              | "creator_oauth_substack_revoked" | "creator_token_refresh_failed",
  creator_id: uuid::Uuid,
  publication_id: Option<uuid::Uuid>,
  timestamp: chrono::DateTime<Utc>,
  status: "success" | "failure" | "pending",
  error_code: Option<String>,
  metadata: {
    scope_requested: vec!["publications.read", ...],
    scope_granted: vec!["publications.read", ...],
    token_expiry_days: 90,
    ...
  }
}
```

---

## 11. Implementation Checklist

- [ ] Register AXIOM app with Substack (client_id, client_secret)
- [ ] Implement `/api/v1/creator/oauth/substack/start` endpoint
- [ ] Implement `/api/v1/creator/oauth/substack/callback` endpoint
- [ ] Implement encrypted keychain storage (AES-256-GCM)
- [ ] Implement session token in Redis
- [ ] Implement token refresh cron job
- [ ] Implement revocation endpoint
- [ ] Add behavioral firewall audit logging
- [ ] Create QA test harness (mock Substack responses)
- [ ] Create error message UI (dashboard integration)
- [ ] Deploy to staging (Aug 1, 2026)
- [ ] Load test: 100 concurrent OAuth flows
- [ ] Security audit: OWASP Top 10 checklist
- [ ] Go-live: Aug 15, 2026

---

## 12. References

- IETF RFC 6749: OAuth 2.0 Authorization Framework
- IETF RFC 6750: OAuth 2.0 Bearer Token Usage
- OWASP: OAuth 2.0 Cheat Sheet
- Substack OAuth API (internal docs, shared via Slack #integrations)

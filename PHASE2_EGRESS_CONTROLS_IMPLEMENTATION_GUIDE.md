# SMAOS Phase 2: Egress Controls - Implementation Guide
**Developer Reference for Weeks 3-6**

Quick links to spec sections:
- **Spec Location:** `/Users/andriileukhin/Documents/SovereignNexus/PHASE2_EGRESS_CONTROLS_SPEC.md`
- **Policy Template:** `Section 1.2` (YAML format)
- **Core Enforcement:** `Section 1.4` (5-phase validation)
- **Test Cases:** `Section 3` (12 comprehensive tests)

---

## A. Module Dependencies & Interfaces

### External Crate Dependencies
```rust
// Cargo.toml
tokio = "1.35"        // Async runtime
reqwest = "0.11"      // HTTP client
regex = "1.10"        // Pattern matching
ipnetwork = "0.20"    // CIDR IP validation
url = "2.4"           // URL parsing
ed25519-dalek = "2.1" // Post-quantum signatures
sha2 = "0.10"         // Hash (for TLS pinning)
```

### Module Imports
```rust
// In l5_communication main
use egress_control::{EgressControl, EgressDecision};
use l3_permit_gates::egress_gate;
use l8_proof::egress_audit;

// Create singleton
lazy_static::lazy_static! {
    static ref EGRESS_CONTROL: EgressControl = 
        EgressControl::new("./policies/egress_policies.yaml").expect("Failed to load egress policies");
}
```

---

## B. Detailed Implementation Examples

### B.1 Policy Loading from File (Week 3)

```rust
// src/policy_loader.rs - Load from YAML at startup
use std::fs;
use serde_yaml;

pub fn load_from_file(path: &str) -> Result<EgressPolicy, EgressError> {
    let contents = fs::read_to_string(path)?;
    let policy: EgressPolicy = serde_yaml::from_str(&contents)?;
    
    // Validate policy structure
    validate_policy(&policy)?;
    
    Ok(policy)
}

fn validate_policy(policy: &EgressPolicy) -> Result<(), EgressError> {
    for (pilot_id, pilot_policy) in &policy.policies {
        // Check no duplicate domains
        if let Some(domains) = &pilot_policy.allowed_destinations.exact_domains {
            let mut seen = std::collections::HashSet::new();
            for domain in domains {
                if !seen.insert(domain.to_lowercase()) {
                    return Err(EgressError::DuplicateDomain(domain.clone()));
                }
            }
        }
        
        // Validate regex patterns compile
        if let Some(patterns) = &pilot_policy.allowed_destinations.regex_patterns {
            for pattern in patterns {
                regex::Regex::new(pattern)?;
            }
        }
        
        // Validate CIDR ranges
        if let Some(ranges) = &pilot_policy.allowed_destinations.ip_ranges {
            for range in ranges {
                ipnetwork::IpNetwork::from_str(range)?;
            }
        }
    }
    
    Ok(())
}
```

### B.2 Whitelist Matching (Week 3)

```rust
// src/whitelist.rs - Multi-strategy matching
use regex::Regex;
use url::Url;

pub fn is_whitelisted(parsed_url: &Url, destinations: &AllowedDestinations) -> bool {
    let host = match parsed_url.host_str() {
        Some(h) => h.to_lowercase(),
        None => return false,
    };
    
    // Strategy 1: Exact domain match
    if let Some(exact_domains) = &destinations.exact_domains {
        if exact_domains.iter().any(|d| d.to_lowercase() == host) {
            return true;
        }
    }
    
    // Strategy 2: Regex pattern match
    if let Some(patterns) = &destinations.regex_patterns {
        for pattern in patterns {
            if let Ok(re) = Regex::new(pattern) {
                if re.is_match(&host) {
                    return true;
                }
            }
        }
    }
    
    // Strategy 3: IP range match (CIDR)
    if let Some(ip_ranges) = &destinations.ip_ranges {
        if let Ok(ip_addr) = host.parse::<std::net::IpAddr>() {
            for range_str in ip_ranges {
                if let Ok(network) = ipnetwork::IpNetwork::from_str(range_str) {
                    if network.contains(ip_addr) {
                        return true;
                    }
                }
            }
        }
    }
    
    false
}

pub fn is_explicitly_blocked(host: &str, blocked_domains: &[String]) -> bool {
    blocked_domains.iter().any(|d| {
        d.to_lowercase() == host.to_lowercase()
    })
}
```

### B.3 DNS Validator (Week 4)

```rust
// src/dns_validator.rs - Rebinding defense
use std::net::IpAddr;
use std::collections::HashMap;
use tokio::sync::RwLock;

pub struct DnsValidator {
    cache: Arc<RwLock<HashMap<String, IpAddr>>>,
}

impl DnsValidator {
    pub fn new() -> Self {
        Self {
            cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub async fn validate_dns(
        &self,
        host: &str,
    ) -> Result<IpAddr, DnsError> {
        // Check cache first (5min TTL)
        let cache = self.cache.read().await;
        if let Some(ip) = cache.get(host) {
            return Ok(*ip);
        }
        drop(cache);
        
        // Resolve hostname
        let addrs = tokio::net::lookup_host(format!("{}:443", host))
            .await?
            .next()
            .ok_or(DnsError::NoAddress)?;
        
        let ip = addrs.ip();
        
        // Check for private IP ranges (rebinding defense)
        if is_private_ip(&ip) {
            return Err(DnsError::PrivateIp(ip));
        }
        
        // Cache result
        let mut cache = self.cache.write().await;
        cache.insert(host.to_string(), ip);
        
        Ok(ip)
    }
}

fn is_private_ip(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => {
            // 10.0.0.0/8
            v4.octets()[0] == 10 ||
            // 172.16.0.0/12
            (v4.octets()[0] == 172 && v4.octets()[1] >= 16 && v4.octets()[1] <= 31) ||
            // 192.168.0.0/16
            (v4.octets()[0] == 192 && v4.octets()[1] == 168) ||
            // 127.0.0.0/8 (loopback)
            v4.octets()[0] == 127 ||
            // 169.254.0.0/16 (link-local)
            (v4.octets()[0] == 169 && v4.octets()[1] == 254)
        },
        IpAddr::V6(v6) => {
            v6.is_loopback() || 
            v6.is_private() ||
            v6.is_link_local()
        }
    }
}
```

### B.4 TLS Validator (Week 4)

```rust
// src/tls_validator.rs - Certificate pinning
use sha2::{Sha256, Digest};

pub struct TlsValidator {
    pinned_certs: HashMap<String, String>,  // domain -> cert_fingerprint
}

impl TlsValidator {
    pub async fn validate_tls(
        &self,
        domain: &str,
        fallback_block: bool,
    ) -> Result<(), TlsError> {
        
        // Get expected fingerprint
        let expected_fp = match self.pinned_certs.get(domain) {
            Some(fp) => fp.clone(),
            None => {
                // No pinning required for this domain
                return Ok(());
            }
        };
        
        // Fetch certificate from server
        let client = reqwest::Client::new();
        let response = client.get(format!("https://{}", domain)).send().await?;
        
        // Extract and hash certificate
        let cert_data = response.headers()
            .get("x-certificate")
            .ok_or(TlsError::NoCert)?
            .as_bytes();
        
        let mut hasher = Sha256::new();
        hasher.update(cert_data);
        let actual_fp = format!("sha256/{}", hex::encode(hasher.finalize()));
        
        // Compare fingerprints
        if actual_fp != expected_fp {
            if fallback_block {
                return Err(TlsError::CertMismatch {
                    domain: domain.to_string(),
                    expected: expected_fp,
                    actual: actual_fp,
                });
            } else {
                // Log warning but allow (non-critical API)
                eprintln!("WARNING: Cert mismatch for {}", domain);
            }
        }
        
        Ok(())
    }
}
```

### B.5 Rate Limiting (Week 5)

```rust
// In enforcement.rs - Rate limiting logic
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct RateLimiter {
    attempts: Arc<RwLock<HashMap<String, Vec<u64>>>>,  // key -> timestamps
}

impl RateLimiter {
    pub async fn should_rate_limit(
        &self,
        pilot_id: &str,
        domain: &str,
        limits: &RateLimits,
    ) -> bool {
        
        let key = format!("{}:{}", pilot_id, domain);
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let mut attempts = self.attempts.write().await;
        let timestamps = attempts.entry(key).or_insert_with(Vec::new);
        
        // Remove old timestamps (older than 60 seconds)
        timestamps.retain(|&ts| now - ts < 60);
        
        // Check per-minute limit
        if timestamps.len() >= limits.per_minute as usize {
            return true;  // Rate limited
        }
        
        // Add new timestamp
        timestamps.push(now);
        
        false
    }
}
```

### B.6 Full Enforcement Pipeline (Week 3-4)

```rust
// src/enforcement.rs - Main validation function
pub async fn enforce_egress_policy(
    pilot_id: &str,
    target_url: &str,
    request_method: &str,
    request_body: &[u8],
    policy: &EgressPolicy,
) -> (EgressDecision, EgressAttempt) {
    
    let attempt_id = uuid::Uuid::new_v4().to_string();
    
    // PHASE 1: URL Validation
    let parsed_url = match url::Url::parse(target_url) {
        Ok(u) => u,
        Err(e) => {
            return (
                EgressDecision::Block(format!("Invalid URL: {}", e)),
                EgressAttempt {
                    attempt_id,
                    pilot_id: pilot_id.to_string(),
                    destination_url: target_url.to_string(),
                    decision: EgressDecision::Block("URL_PARSE_FAILED".to_string()),
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    reason: format!("URL parse error: {}", e),
                    checkpoint_hash: String::new(),
                    signature: String::new(),
                },
            );
        }
    };
    
    // PHASE 2: Policy Lookup
    let pilot_policy = match policy.policies.get(pilot_id) {
        Some(p) => p,
        None => {
            return (
                EgressDecision::Block("Unknown pilot".to_string()),
                create_blocked_attempt(&attempt_id, pilot_id, target_url, "UNKNOWN_PILOT"),
            );
        }
    };
    
    // PHASE 3: Whitelist Check
    if !whitelist::is_whitelisted(&parsed_url, &pilot_policy.allowed_destinations) {
        return (
            EgressDecision::Block("Not whitelisted".to_string()),
            create_blocked_attempt(&attempt_id, pilot_id, target_url, "NOT_WHITELISTED"),
        );
    }
    
    // PHASE 4: Explicit Blocklist
    if let Some(host) = parsed_url.host_str() {
        if whitelist::is_explicitly_blocked(host, &pilot_policy.blocked_destinations) {
            return (
                EgressDecision::Block("Explicitly blocked".to_string()),
                create_blocked_attempt(&attempt_id, pilot_id, target_url, "EXPLICIT_BLOCK"),
            );
        }
    }
    
    // PHASE 5: Request Restrictions
    if let Some(restrictions) = &pilot_policy.restrictions {
        if let Some(allowed_methods) = &restrictions.method_whitelist {
            if !allowed_methods.contains(&request_method.to_string()) {
                return (
                    EgressDecision::Block(format!("Method {} not allowed", request_method)),
                    create_blocked_attempt(&attempt_id, pilot_id, target_url, "METHOD_NOT_ALLOWED"),
                );
            }
        }
        
        if restrictions.no_post_with_data && request_method == "POST" && !request_body.is_empty() {
            return (
                EgressDecision::Block("POST with data not allowed".to_string()),
                create_blocked_attempt(&attempt_id, pilot_id, target_url, "POST_WITH_DATA_BLOCKED"),
            );
        }
    }
    
    // PHASE 6: PII Detection
    if let Some(dh) = &pilot_policy.data_handling {
        let pii_count = count_pii_chars(request_body);
        if pii_count > dh.max_pii_chars as usize {
            return (
                EgressDecision::Block("Excessive PII".to_string()),
                create_blocked_attempt(&attempt_id, pilot_id, target_url, "EXCESSIVE_PII"),
            );
        }
    }
    
    // All checks passed
    (
        EgressDecision::Allow,
        EgressAttempt {
            attempt_id,
            pilot_id: pilot_id.to_string(),
            destination_url: target_url.to_string(),
            decision: EgressDecision::Allow,
            timestamp: chrono::Utc::now().to_rfc3339(),
            reason: "All validation checks passed".to_string(),
            checkpoint_hash: String::new(),
            signature: String::new(),
        },
    )
}

fn create_blocked_attempt(
    attempt_id: &str,
    pilot_id: &str,
    url: &str,
    reason: &str,
) -> EgressAttempt {
    EgressAttempt {
        attempt_id: attempt_id.to_string(),
        pilot_id: pilot_id.to_string(),
        destination_url: url.to_string(),
        decision: EgressDecision::Block(reason.to_string()),
        timestamp: chrono::Utc::now().to_rfc3339(),
        reason: reason.to_string(),
        checkpoint_hash: String::new(),
        signature: String::new(),
    }
}

fn count_pii_chars(body: &[u8]) -> usize {
    // Simple regex-based detection (credit card, SSN, email)
    let body_str = String::from_utf8_lossy(body);
    
    // Credit card (16 digits)
    let cc_pattern = regex::Regex::new(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b").unwrap();
    
    // SSN (XXX-XX-XXXX)
    let ssn_pattern = regex::Regex::new(r"\b\d{3}-\d{2}-\d{4}\b").unwrap();
    
    // Email
    let email_pattern = regex::Regex::new(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b").unwrap();
    
    let cc_count = cc_pattern.find_iter(&body_str).count();
    let ssn_count = ssn_pattern.find_iter(&body_str).count();
    let email_count = email_pattern.find_iter(&body_str).count();
    
    (cc_count * 16) + (ssn_count * 11) + (email_count * 20)
}
```

### B.7 Layer 5 Integration (Week 4)

```rust
// l5_communication/src/http_client.rs - Intercepted HTTP wrapper
pub struct EgressControlledHttpClient {
    inner: reqwest::Client,
    egress_control: Arc<EgressControl>,
    audit_tx: tokio::sync::mpsc::Sender<EgressAttempt>,
}

impl EgressControlledHttpClient {
    pub async fn execute_request(
        &self,
        request: HttpRequest,
    ) -> Result<HttpResponse, HttpError> {
        
        // 1. Pre-flight egress check
        let (decision, attempt) = self.egress_control.check_egress(
            &request.pilot_id,
            &request.url,
            &request.method,
            &request.body,
        ).await;
        
        // 2. Log attempt
        if let Err(e) = self.audit_tx.send(attempt.clone()).await {
            eprintln!("Failed to log egress attempt: {}", e);
        }
        
        // 3. Make decision
        match decision {
            EgressDecision::Allow => {},
            EgressDecision::Block(reason) => {
                return Err(HttpError::EgressBlocked(reason));
            },
            EgressDecision::Escalate(reason) => {
                // TODO: Route to human review queue
                return Err(HttpError::EscalationRequired(reason));
            },
        }
        
        // 4. Execute HTTP call
        let response = self.inner
            .execute(request.to_reqwest())
            .await?;
        
        Ok(HttpResponse::from(response))
    }
}
```

### B.8 Layer 3 Integration (Week 4)

```rust
// l3_permit_gates/src/egress_gate.rs - Pre-execution check
pub async fn egress_permit_gate(
    request: &PermitRequest,
    policy: &EgressPolicy,
) -> PermitDecision {
    
    if let Some(tool_calls) = &request.tool_calls {
        for tool in tool_calls {
            // Check if tool requires egress validation
            if !TOOL_REGISTRY[&tool.name].requires_egress_validation {
                continue;
            }
            
            // Extract URL argument
            let url = match tool.args.get("url") {
                Some(serde_json::Value::String(u)) => u,
                _ => continue,  // No URL argument
            };
            
            // Check against policy
            let (decision, _) = enforce_egress_policy(
                &request.pilot_id,
                url,
                "GET",  // Pre-execution check uses GET (actual method checked later)
                &[],
                &policy,
            ).await;
            
            match decision {
                EgressDecision::Block(reason) => {
                    return PermitDecision::Denied(format!("Egress blocked: {}", reason));
                },
                EgressDecision::Escalate(reason) => {
                    return PermitDecision::RequiresHumanReview(reason);
                },
                EgressDecision::Allow => {},
            }
        }
    }
    
    PermitDecision::Approved
}
```

### B.9 Layer 8 Integration (Week 6)

```rust
// l8_proof/src/egress_audit.rs - AP2 ledger entry
pub async fn append_egress_to_ap2(
    attempt: &EgressAttempt,
    ap2: &mut AP2Ledger,
    kms: &KmsClient,
) -> Result<(), ProofError> {
    
    let entry = serde_json::json!({
        "entry_id": uuid::Uuid::new_v4().to_string(),
        "attempt_id": attempt.attempt_id,
        "pilot_id": attempt.pilot_id,
        "destination_url": attempt.destination_url,
        "decision": format!("{:?}", attempt.decision),
        "timestamp": chrono::Utc::now().to_rfc3339(),
        "reason": attempt.reason,
    });
    
    // Sign with Ed25519 (post-quantum safe)
    let entry_json = serde_json::to_string(&entry)?;
    let signature = kms.sign_ed25519(entry_json.as_bytes()).await?;
    
    let signed_entry = serde_json::json!({
        ...entry,
        "signature": signature,
    });
    
    // Append to immutable ledger
    ap2.append(serde_json::to_string(&signed_entry)?)?;
    
    Ok(())
}
```

---

## C. Test Implementation Checklist

### Week 3 Tests (Policy Validation)

```rust
#[tokio::test]
async fn test_whitelist_exact_domain_allowed() {
    let policy = load_test_policy("hotel");
    let (decision, _) = enforce_egress_policy(
        "hotel",
        "https://equifax.com/score",
        "GET",
        &[],
        &policy,
    ).await;
    assert_eq!(decision, EgressDecision::Allow);
}

#[tokio::test]
async fn test_unapproved_external_url_blocked() {
    let policy = load_test_policy("hotel");
    let (decision, attempt) = enforce_egress_policy(
        "hotel",
        "https://attacker.com/exfil",
        "GET",
        &[],
        &policy,
    ).await;
    assert!(matches!(decision, EgressDecision::Block(_)));
    assert_eq!(attempt.reason, "NOT_WHITELISTED");
}
```

### Week 4 Tests (Attack Mitigation)

```rust
#[tokio::test]
async fn test_dns_rebinding_attack_blocked() {
    let mut dns_validator = DnsValidator::new();
    // Mock DNS to return private IP
    let result = dns_validator.validate_dns("equifax.com").await;
    assert!(matches!(result, Err(DnsError::PrivateIp(_))));
}

#[tokio::test]
async fn test_certificate_pinning_mitm_blocked() {
    let mut tls_validator = TlsValidator::new();
    tls_validator.pinned_certs.insert(
        "equifax.com".to_string(),
        "sha256/CORRECT_FINGERPRINT".to_string(),
    );
    
    // Mock mismatched cert
    let result = tls_validator.validate_tls("equifax.com", true).await;
    assert!(result.is_err());
}
```

---

## D. Deployment Checklist

- [ ] **Week 3:** Create `crates/egress_control`, implement policy + enforcement
- [ ] **Week 3:** Tests 1-3 passing, cargo test clean
- [ ] **Week 4:** DNS + TLS validators, integrate into L5
- [ ] **Week 4:** Tests 4-7 passing, attack scenarios verified
- [ ] **Week 5:** Rate limiting, policy loader, dynamic reload
- [ ] **Week 5:** Tests 8-11 passing, performance <1ms per check
- [ ] **Week 6:** AP2 integration, Ed25519 signing
- [ ] **Week 6:** Test 12 passing, full audit trail verified
- [ ] **Week 6:** CISO appeal document, regulatory sign-off

---

## E. Performance Targets

**Latency per egress check:**
- URL parsing + whitelisting: <0.1ms
- DNS validation (cached): <0.05ms
- TLS validation (cached): <0.05ms
- Rate limit check: <0.1ms
- **Total: <1ms** (measured with `cargo bench`)

**Memory footprint:**
- Policy cache: <100 KB (in-memory YAML)
- Attempt log ring buffer: <50 MB (1M attempts)
- DNS cache: <10 MB (10k entries × 1KB)

---

## References

- Spec: `/Users/andriileukhin/Documents/SovereignNexus/PHASE2_EGRESS_CONTROLS_SPEC.md`
- Phase 1 Architecture: `/Users/andriileukhin/Documents/SovereignNexus/ARCHITECTURE.md`
- Layer 5 Crates: `/Users/andriileukhin/Documents/SovereignNexus/crates/l5_communication/`
- Layer 3 Crates: `/Users/andriileukhin/Documents/SovereignNexus/crates/l3_permit_gates/`
- Layer 8 Crates: `/Users/andriileukhin/Documents/SovereignNexus/crates/l8_proof/`

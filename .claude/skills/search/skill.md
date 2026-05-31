# Skill: /search — Sovereign Search Router (Opt-In External Escalation)

## Status
**Phase:** Architecture Locked (Implementation deferred to Phase 2, post-Israel)  
**Trigger:** `/search [query]` (reserved for future use)  
**Availability:** June 6+ (after patent filing + Israel demo)

## Vision
Deterministic, sovereignty-aligned search that:
- **Local-first by default** (SQLite cache, pre-ingested knowledge)
- **Opt-in external escalation** (Perplexity, Bing, fallback to local)
- **Cryptographically audited** (every query Merkle-rooted to `EXEC_LOG.json`)
- **Covenant-aligned** (1%/99% applied to API spend; no extraction without logging)

## Architecture (To Be Implemented Post-Israel)

### SearchProvider Trait
```rust
pub trait SearchProvider: Send + Sync {
    async fn query(&self, q: &str, opts: SearchOpts) -> Result<SearchResult>;
    fn name(&self) -> &'static str;
}

pub struct SearchResult {
    pub answer: String,
    pub sources: Vec<Source>,
    pub confidence: f64,
    pub covenant_check: CovenantVerification,
}
```

### SovereignSearchRouter Logic
```
[User Query /search "..."]
    ↓
[Local Cache Check] (SHA-256 keyed, 24h TTL)
    ├─ Cache HIT + fresh → Return local result
    └─ Cache MISS or stale → Continue
    ↓
[Time-Sensitivity Analysis] (is this query deadline-critical?)
    ├─ NOT critical + SMAOS_CLOUD_SEARCH=false → Return cached/stale warning
    └─ Critical + SMAOS_CLOUD_SEARCH=true → Escalate to external
    ↓
[External Escalation] (round-robin: Perplexity → Bing → local fallback)
    ├─ Response received → Sanitize (strip tracking, ads, metadata)
    ├─ Cache sanitized result (SHA-256 keyed)
    └─ Audit log to EXEC_LOG.json (Merkle-rooted, Ed25519-signed)
    ↓
[Covenant Check] (NLI scan: "Does answer align with 1%/99% values?")
    ├─ Aligned → Return with ✅ covenant verification
    └─ Breach detected → Return with ⚠️ flag + human review required
```

### Implementation Modules (Post-Israel)
- `src/search/router.rs` — SovereignSearchRouter trait + router logic
- `src/search/cache.rs` — SqliteCache (SHA-256 keyed, TTL management)
- `src/search/providers/perplexity.rs` — Perplexity adapter (keychain auth, sanitization)
- `src/search/providers/bing.rs` — Bing fallback adapter
- `src/search/audit.rs` — Merkle-rooted audit logging
- `src/search/covenant.rs` — Economic intent verification (1%/99% alignment)

## Personal Mode Guardrails (Non-Negotiable)

| Guardrail | Enforcement |
|-----------|------------|
| **Opt-In Only** | `SMAOS_CLOUD_SEARCH=false` by default; no external queries without explicit flag |
| **No PII Leakage** | Query sanitizer removes personal identifiers before external send |
| **Encrypted Credentials** | API keys stored in OS keychain; never in env or logs |
| **Local Fallback** | If external fails or disabled, return cached result with "stale data" warning |
| **Audit Trail** | Every query + response hashed → Merkle-rooted → private `EXEC_LOG.json` |
| **Covenant Check** | Post-response NLI: "Aligned with 1%/99%?" Flag breaches for human review |

## Usage Examples (Future)

```text
/search "What are the latest Series A market multiples for sovereign AI (June 2026)?"
→ Router escalates (time-critical market data)
→ Perplexity fetches live data
→ Response sanitized + cached + audited
→ Covenant check: "Does investor positioning align?" ✅

/search "RCE patents filed since 2024"
→ Router escalates (patent research)
→ Bing fallback (if Perplexity unavailable)
→ Response cached for 24h
→ Audit trail: query_hash + response_hash Merkle-rooted

/search "local knowledge only: RCE implementation patterns"
→ Router stays local (explicit local-only keyword)
→ Returns pre-ingested knowledge from SQLite
→ Zero external call
```

## Roadmap

- **June 2:** Patent filing (critical path)
- **June 3–5:** Israel demo (no coding)
- **June 6:** SSR Phase 2 implementation begins
  - [ ] SearchProvider trait + SovereignSearchRouter core logic
  - [ ] SqliteCache with SHA-256 keying + 24h TTL
  - [ ] Perplexity adapter (keychain auth, response sanitization)
  - [ ] Bing fallback adapter
  - [ ] Audit logger (Merkle-rooted EXEC_LOG append)
  - [ ] Covenant checker (1%/99% alignment NLI)
  - [ ] Property tests: opt-in enforcement, cache freshness, covenant alignment
  - [ ] Integration with `/decide` for strategic queries

## Why Sovereign Search Router?

| Dimension | Local-Only | With SSR |
|-----------|-----------|---------|
| **Default behavior** | Cached knowledge (stale but sovereign) | Same (cloud is opt-in) |
| **Time-critical queries** | Degraded (stale data) | Augmented (real-time data) |
| **Audit compliance** | Local actions only | All queries Merkle-rooted |
| **Sovereignty cost** | $0 | ~$0.01/query (when used) |
| **Decision confidence** | Lower (pre-ingested data) | Higher (live market data) |

**Result:** Maximum capability (live data) + maximum sovereignty (opt-in, audited, local-fallback).

---

## ✅ Reserved for Future Implementation

This skill is **architecturally locked** but **not yet implemented**. It serves as a commitment to sovereign search capability without sacrificing the critical 48-hour window before Israel deployment.

**Next trigger:** Post-Israel (June 6), when patent filing is complete and demo is proven.

# IP Protection Protocol: Opaque Core, Transparent Edges

**Status:** LOCKED for immediate implementation  
**Date:** June 1, 2026  
**Doctrine:** Hide mechanisms. Share philosophy. Protect the physics layer. Reveal the narrative.

---

## Core Principle

> **"No component leaves the system unless it increases the system's power."**

Your frontier architecture is defensible only if:
1. **Core invariants stay sealed** (routing logic, memory constitution, pricing grids, trust index, replenishment pipeline, governance rules)
2. **Edges stay transparent** (APIs, capsules, guarantees, philosophy, ethics)
3. **Narrative is public, mechanisms are private**

This is the pattern used by SpaceX (flight software), Palantir (Foundry), DeepMind (Alpha), Tesla (Autopilot), Apple (silicon), Nvidia (kernels), Stripe (fraud models).

---

## What Stays Sealed (Opaque Core)

**These are your crown jewels. Protect like semiconductor fab lithography recipes.**

### Layer 1: Computation
- `TrustHashIndex` implementation details (perfect hash codegen, mmap layout, page-locking strategy)
- `BlastMatrixCache` grid generation algorithm (how you choose risk/demand discretization, interpolation heuristics)
- `ReplenishmentWorker` data sources (which market APIs, which regulatory feeds, weight coefficients)
- `AndonBreaker` thresholds and fallback heuristics

### Layer 2: Economics
- Pricing grid values (the 64×64×64 matrix is your alpha)
- Trust score weights (which agents get high scores, why)
- Covenant premium percentages (how much you extract for sovereignty)
- Dynamic adjustment bounds (your elastic policy envelope)

### Layer 3: Governance
- Ratification rules (how Tier 2 → Tier 0 promotion decisions are made)
- Human Gate criteria (what triggers escalation)
- Merkle versioning strategy (how you version-hash tables)
- Fallback decision tree logic (what happens on Tier 0 breach)

### Layer 4: Architecture
- Hot-path memory layout (cache alignment, SIMD vectorization strategy)
- Tier 0/1/2 boundary enforcement (implementation of the latency constitution)
- Andon thresholds (specific nanosecond targets for each operation)
- Cryptographic key management (how Merkle roots are signed, stored, rotated)

---

## What Stays Transparent (Transparent Edges)

**These are your moat. Share them to attract allies and build network effects.**

### Public Philosophy
- Sovereign compute doctrine (you control your infrastructure, not clouds)
- Covenant economics (1%/99% split, beneficiary alignment)
- O(1) discipline (no thinking on hot path)
- Planetary governance (latency as justice)

### Public Interfaces
- Capsule definition (what agents can call)
- Return guarantees (Tier 0: 1–20ns, Tier 1: 100µs–10ms, Tier 2: async)
- Error semantics (fail-closed vs. fallback)
- API documentation

### Public Narratives
- Why O(1) matters (system stability, predictability, fairness)
- Why sealed cores matter (competitive advantage, sovereign control)
- Why transparent edges matter (trust, adoption, ecosystem)
- Why latency is governance (speed = power, and power should be just)

### Public Proofs
- Architecture diagrams (high-level, no internals)
- Benchmark results (p99 latency, cache hit rates, throughput)
- Merkle audit trails (you can prove your system evolved correctly)
- Third-party validation (external audits of latency guarantees, without revealing mechanisms)

---

## Progressive Disclosure Rules

**You don't need to expose everything to everyone.**

### Tier 0: Public (World)
- Philosophy
- High-level diagrams
- Non-critical modules
- API signatures
- Latency guarantees

### Tier 1: Partners (Early Clients, Strategic Integrators)
- Capsule internals
- Interface details
- Error handling code
- Benchmark harness (so they can verify independently)
- **NOT:** Grid values, trust weights, ratification rules

### Tier 2: Contractors (On Your Payroll)
- Phase 2–4 implementation code
- TrustHashIndex + BlastMatrixCache internals
- ReplenishmentWorker pipeline
- **NOT:** Pricing grid, trust score weights, human gate criteria

### Tier 3: You Only (Core IP)
- Grid generation algorithm and inputs
- Trust score weighting scheme
- Ratification decision rules
- Fallback heuristics
- Merkle versioning strategy
- Cryptographic key material

---

## Covenant Firewall for Your Own IP

Define a rule for every potential disclosure:

> **"Does sharing this component increase the system's power?"**

**YES → Share it:**
- Increases adoption (more agents using your capsules)
- Increases trust (external audits validate your latency guarantees)
- Increases network effects (more ecosystem partners)
- Increases your leverage (standards advantage, first-mover moat)

**Examples:** APIs, philosophy, benchmark results, audit trails

**NO → Seal it:**
- Reduces your advantage (competitors could copy)
- Reveals your invariants (they'd understand your governance logic)
- Exposes your physics (they'd reverse-engineer your pricing)
- Enables attackers (they'd target your actual thresholds)

**Examples:** Grid values, trust weights, ratification rules, replenishment sources

---

## Strategic Narrative (Public)

**You can talk about:**
- Sovereign compute (you own your infrastructure and decisions)
- Planetary governance (latency encodes justice)
- O(1) discipline (predictable, fail-closed systems)
- Capsule economy (agents as economic units)
- Covenant ethics (1%/99% beneficiary alignment)
- Merkle provenance (cryptographic proof of integrity)

**You cannot talk about:**
- Your grid resolution (64×64×64 discretization)
- Your trust weighting (which agents score high and why)
- Your pricing premiums (how much you extract)
- Your andon thresholds (specific nanosecond cutoffs)
- Your replenishment sources (which APIs you scrape)
- Your ratification algorithm (how Tier 2 proposals are approved)

**Why:** Narrative attracts allies. Mechanisms attract attackers.

---

## Secrecy Perimeter Architecture

**Protect the hot path like a semiconductor fab.**

- **Memory-resident sealed modules** (Tier 0 code never touches disk after initial compile)
- **No remote debugging** (SSH access disabled on production machines running Tier 0)
- **No dynamic linking** (all dependencies compiled statically into the hot path)
- **No runtime configuration** (grid values, trust scores, thresholds are all burned in at compile time)
- **No external dependencies** (Tier 0 has zero network calls)
- **No cloud execution** (hot path runs on isolated, air-gapped hardware)

If someone doesn't have **physical access** to the machine, they don't have access to the physics.

---

## Evolution Loop (Offline-First)

Your innovation pipeline:

1. **Research** (online)  
   - Web scraping, regulatory monitoring, market signals  
   - Happens in Tier 2, async, in the background

2. **Synthesis** (offline)  
   - Grid generation, trust reweighting, threshold tuning  
   - Happens on your local machine, not in cloud, not on CI/CD

3. **Ratification** (you only)  
   - Human review of proposed changes  
   - Manual approval via Human Gate

4. **Promotion to Tier 0/1** (atomic swap)  
   - Merkle-hash the new grid/index
   - Verify signatures
   - Atomic file swap (no incremental updates)
   - Log to EXEC_LOG.private.json

**Result:** No one sees your intermediate ideas, failures, heuristics, or data sources. Only the final, hardened, Merkle-rooted version ever touches runtime.

This is how hedge funds protect alpha.  
This is how cryptography teams protect primitives.  
This is how sovereign compute protects itself.

---

## Implementation Checklist

- [ ] Identify all Tier 0 code (hot path modules)
- [ ] Apply memory-resident + no-remote-debug restrictions
- [ ] Seal all pricing grid files (chmod 600, only you can read)
- [ ] Seal all trust score weights (hard-coded, not configurable)
- [ ] Seal all ratification rules (code review only, never exposed)
- [ ] Codify Progressive Disclosure rules in onboarding docs
- [ ] Separate public repo (philosophy, APIs, diagrams) from private repo (mechanisms, grids, ratification)
- [ ] Establish Covenant Firewall: review every disclosure against "increases system power?" rule
- [ ] Implement offline evolution loop (web → synthesis → ratification → atomic swap)
- [ ] Document what stays secret forever vs. what becomes public post-exit
- [ ] Brief all contractors on disclosure boundaries

---

## References

- Latency Constitution: What you're protecting (Tier 0/1/2 physics)
- Phase 2–4: Implementation (what contractors see vs. what stays sealed)
- Protocol v2: Capsule interface (what's public API vs. what's internal)
- DECISION-DB: Where Tier 2 proposals are logged (before promotion)

---

**The perimeter is locked. The core is opaque. The edges are transparent. Execute.**

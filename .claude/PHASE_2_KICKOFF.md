# Phase 2 Kickoff: Rapid-MLX Deployment & Chaos Petri Quarantine (Weeks 4–6)

**Status:** Ready to execute  
**Gate:** Phase 1 complete + hardware delivery signed off  
**Deliverable:** Live Rapid-MLX cluster + failure injection testing framework

---

## Phase 2 Overview

**Duration:** Weeks 4–6 (3 weeks)  
**Critical Path:**
1. Mac Studio Ultra nodes arrive + flashed with Rapid-MLX
2. Establish local 10Gbps networking (inter-node communication)
3. Deploy Chaos Petri Quarantine Zone (failure injection for resilience)
4. Execute Sneakernet Ingress (offline model weight transfer with dual-auth)
5. Run live agent swarm hypothesis generation on local cluster

**Success Criteria:**
- ✓ All 5 nodes operational (Rapid-MLX inference < 100ms latency)
- ✓ 10Gbps networking verified (inter-node throughput > 1GB/s)
- ✓ Chaos Petri tests prove fault tolerance (agents survive node failure)
- ✓ Model weights transferred securely (dual-auth, no plaintext on network)
- ✓ 3–5 agents running simultaneously on local cluster

---

## Hardware Delivery Checklist (Week 4)

### Pre-Arrival (Week 3)

- [ ] Confirm Mac Studio Ultra specifications (M4 Max, 128GB unified memory)
- [ ] Order networking gear (5× 10Gbps Ethernet adapters, CAT8 cables)
- [ ] Prepare HPE rack (power, cooling, network ports)
- [ ] Stage Rapid-MLX binary + model weights
- [ ] Test provisioning playbook on dev machine

### On-Arrival (Week 4)

- [ ] Unbox and verify serial numbers (5 units)
- [ ] Install 10Gbps Ethernet adapters (one per node)
- [ ] Connect nodes to HPE rack network (isolated VLAN)
- [ ] Boot into recovery mode
- [ ] Flash Rapid-MLX engine (using `phase2_flash_rapid_mlx.sh` script)
- [ ] Load Qwen 3.5-4B model (Q4 quantization, ~3GB per node)
- [ ] Verify inference on all 5 nodes (< 100ms TTFT cached)

---

## Task P2-1: Rapid-MLX Cluster Deployment

**Owner:** Agent B (agent-inference worktree)  
**Duration:** Week 4 (3 days delivery + 2 days setup)

### Subtasks

1. **Create provisioning playbook** (`scripts/provision_rapid_mlx.sh`)
   - Flash Rapid-MLX on each node via SSH
   - Load model weights from Sneakernet (see Task P2-3)
   - Verify inference latency benchmark

2. **Setup monitoring dashboard**
   - Track inference metrics (TTFT, throughput, errors)
   - Monitor GPU/CPU utilization
   - Log failures (for Chaos Petri integration)

3. **Establish inter-node communication**
   - Configure 10Gbps network (IP allocation, MTU tuning)
   - Test throughput with `iperf3` (target: > 1GB/s per pair)
   - Setup health checks (ping, SSH availability)

4. **Integration test**
   - Single agent inference on Node 1
   - Agent → Node 2 inference (over network)
   - All 5 nodes responsive + consistent latency

### Deliverable

**Script:** `scripts/provision_rapid_mlx.sh`

```bash
#!/bin/bash
# Provision all 5 Mac Studio Ultra nodes

for i in {1..5}; do
    node_ip="10.0.0.$((100 + i))"
    echo "Flashing Rapid-MLX on node-$i ($node_ip)..."
    
    ssh -i ~/.ssh/prague_deploy_key user@$node_ip \
        'curl -O https://builds.sovereignai.eu/rapid_mlx_universal && \
         chmod +x rapid_mlx_universal && \
         ./rapid_mlx_universal --flash-mode && \
         ./rapid_mlx_universal --load-model Qwen3.5-4B-Q4'
    
    echo "✓ node-$i ready"
done

# Benchmark
echo "Running inference benchmark..."
for i in {1..5}; do
    ssh user@10.0.0.$((100 + i)) \
        'rapid_mlx_cli --bench --iterations=10' | grep TTFT
done
```

---

## Task P2-2: Chaos Petri Quarantine Zone

**Owner:** Agent C (agent-knowledge-graph worktree) + new module  
**Duration:** Week 5 (4 days design + 3 days implementation)

### Purpose

Chaos Petri is a failure injection framework that tests agent resilience. It simulates:
- Node failure (network partition)
- Inference timeout (hardware stall)
- Model corruption (checksum mismatch)
- Concurrent requests (load testing)

### Architecture

**Location:** `crates/siss-chaos-petri/src/lib.rs` (NEW CRATE)

**Core Types:**

```rust
pub struct ChaosPetriQuarantine {
    agents: Vec<AgentId>,
    failure_scenarios: Vec<FailureScenario>,
    recovery_strategies: Vec<RecoveryStrategy>,
    execution_log: Vec<ExecutionEvent>,
}

pub enum FailureScenario {
    NodeDown { node_id: usize, duration: Duration },
    NetworkPartition { nodes: Vec<usize> },
    InferenceTimeout { agent_id: AgentId, latency_ms: u32 },
    ModelCorruption { node_id: usize, checksum_mismatch: bool },
}

pub enum RecoveryStrategy {
    Failover { backup_node: usize },
    Retry { max_attempts: u32, backoff: Duration },
    CircuitBreaker { threshold: f64, timeout: Duration },
}

pub struct ExecutionEvent {
    timestamp: DateTime<Utc>,
    scenario: FailureScenario,
    response: AgentResponse,
    recovery_time_ms: u32,
    success: bool,
}
```

**Test Matrix (12 scenarios):**

1. **Single Node Failure** → Agents failover to replica
2. **Network Partition (3 vs 2)** → Majority quorum elected
3. **Cascading Failures** → Circuit breaker prevents cascade
4. **Inference Timeout** → Fallback to backup inference
5. **Model Corruption** → Checksum validation catches mismatch
6. **Concurrent Requests** → Load balancer distributes queries
7. **Recovery Time** → System recovers in < 5s
8. **Data Consistency** → All nodes agree on state
9. **Agent Isolation** → One agent's failure doesn't crash others
10. **Graceful Degradation** → Reduced capacity vs. total failure
11. **Byzantine Agent** → System detects + isolates bad actor
12. **Rapid Oscillation** → Prevent flapping (recover once, don't thrash)

### Deliverable

**Crate:** `crates/siss-chaos-petri/src/lib.rs`

```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_single_node_failure_triggers_failover() { }
    
    #[test]
    fn test_network_partition_quorum_election() { }
    
    #[test]
    fn test_cascading_failures_halted_by_circuit_breaker() { }
    
    #[test]
    fn test_recovery_time_under_5_seconds() { }
    
    #[test]
    fn test_data_consistency_after_failure() { }
    
    // ... 7 more
}
```

---

## Task P2-3: Sneakernet Ingress (Model Weight Transfer)

**Owner:** Agent D (agent-mandates worktree) + security gate  
**Duration:** Week 5 (2 days implementation)

### Purpose

Transfer 50GB+ model weights from air-gapped storage (USB) to cluster without exposing to network. Dual-auth ensures no single person can do transfer alone.

### Protocol

1. **USB Preparation** (offline, in vault)
   - Encrypt Qwen 3.5-4B weights (AES-256-GCM)
   - Compute SHA256 checksums
   - Store on encrypted USB drive

2. **Dual-Key Extraction**
   - Key Custodian A (CEO): holds private key A
   - Key Custodian B (CTO): holds private key B
   - Decrypt requires both signatures (threshold crypto)

3. **Transfer Ritual**
   ```bash
   # At HPE rack (no network)
   
   # Step 1: Custodian A inserts USB, signs intent
   openssl dgst -sha256 -sign key_a.pem sneakernet_manifest.txt > sig_a.bin
   
   # Step 2: Custodian B verifies + signs approval
   openssl dgst -sha256 -sign key_b.pem sneakernet_manifest.txt > sig_b.bin
   
   # Step 3: System verifies both signatures, unlocks decryption key
   gpg --decrypt --key-split sig_a.bin sig_b.bin > master_key
   
   # Step 4: Load weights into each node
   for node in {1..5}; do
       scp -i secure_key encrypted_weights_Q4.tar.gz node-$node:/local/models/
       ssh node-$node 'openssl enc -d -aes-256-gcm < weights.tar.gz.enc | tar xz'
       ssh node-$node 'sha256sum -c weights_manifest.txt'  # Verify
   done
   ```

### Deliverable

**Security Gate:** `crates/siss-gatekeeper/src/sneakernet_ingress.rs`

```rust
pub struct SneakernetManifest {
    model_name: String,
    model_size_bytes: u64,
    checksum_sha256: String,
    encryption_method: String,  // AES-256-GCM
    required_signatures: usize,  // 2 (dual-auth)
    transfer_timestamp: DateTime<Utc>,
}

pub struct DualAuthTransfer {
    manifest: SneakernetManifest,
    signature_a: Vec<u8>,  // Custodian A
    signature_b: Vec<u8>,  // Custodian B
}

impl DualAuthTransfer {
    pub fn verify(&self) -> Result<(), String> {
        // Both signatures must be valid
        verify_signature_a(&self.signature_a)?;
        verify_signature_b(&self.signature_b)?;
        Ok(())
    }
    
    pub fn unlock_transfer_key(&self) -> Result<Vec<u8>, String> {
        self.verify()?;
        // Reconstruct master key from both signatures (threshold crypto)
        threshold_decrypt(&self.signature_a, &self.signature_b)
    }
}
```

**Test:** Dual-auth key recovery requires both signatures (single signature insufficient)

---

## Task P2-4: Live Agent Swarm Demo

**Owner:** Agent E (agent-integration worktree)  
**Duration:** Week 6 (final integration)

### What It Shows

1. 3–5 agents spawn on local Rapid-MLX cluster
2. Each agent runs hypothesis generation independently
3. Agents communicate via local network (< 1ms latency)
4. CapsuleCommitActor merges their commits in parallel
5. Chaos Petri injects failures mid-execution
6. System recovers gracefully (agents survive)

### Script

**Location:** `crates/siss-agent-shell/examples/phase2_swarm_demo.rs`

```rust
#[tokio::main]
async fn main() -> Result<()> {
    // Initialize cluster (all 5 nodes healthy)
    let cluster = RapidMLXCluster::connect(vec![
        "10.0.0.101", "10.0.0.102", "10.0.0.103", "10.0.0.104", "10.0.0.105"
    ]).await?;
    
    println!("✓ Cluster connected (5/5 nodes)");
    
    // Spawn 5 agents
    let agents = spawn_agents(5, &cluster).await?;
    println!("✓ 5 agents spawned");
    
    // Run hypothesis generation for 2 minutes
    for iteration in 1..=5 {
        println!("\n--- Iteration {} ---", iteration);
        
        // Each agent generates hypothesis independently
        let hypotheses = futures::future::join_all(
            agents.iter().map(|a| a.generate_hypothesis())
        ).await?;
        
        // CapsuleCommitActor merges their changes
        let decisions = orchestrator.ingest_all(
            hypotheses.into_iter().map(|h| h.to_capsule()).collect()
        ).await?;
        
        println!("✓ Iteration {}: {} commits approved", iteration, decisions.len());
        
        // Chaos Petri injects failure on iteration 3
        if iteration == 3 {
            println!("⚡ CHAOS: Injecting node-3 failure");
            chaos_petri.fail_node(3).await?;
            tokio::time::sleep(Duration::from_secs(2)).await;
            
            println!("  Agents re-routing to backup nodes...");
            let recovery = cluster.wait_recovery(Duration::from_secs(5)).await?;
            println!("✓ Recovered in {}ms", recovery);
        }
    }
    
    println!("\n✓ Demo complete: all agents survived Chaos Petri injection");
    Ok(())
}
```

---

## Phase 2 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|-----------------|
| Node Availability | 5/5 | `cluster.health_check()` returns all green |
| Inference Latency | < 100ms cached | `cargo run --example phase2_swarm_demo` reports times |
| Network Throughput | > 1GB/s per pair | `iperf3 -c node-2 -R` shows bandwidth |
| Chaos Petri Recovery | < 5 seconds | Failure injection log shows recovery timestamp |
| Agent Swarm Size | 5 agents parallel | Demo runs 5 agents simultaneously |
| Commit Throughput | 10+ commits/min | CapsuleCommitActor approval rate |

---

## Phase 2 Deliverables

| Artifact | Location | Owner | Status |
|----------|----------|-------|--------|
| **Rapid-MLX Provisioning** | `scripts/provision_rapid_mlx.sh` | Agent B | TBD |
| **Chaos Petri Framework** | `crates/siss-chaos-petri/src/lib.rs` | Agent C | TBD |
| **Sneakernet Ingress Gate** | `crates/siss-gatekeeper/src/sneakernet_ingress.rs` | Agent D | TBD |
| **Swarm Demo** | `examples/phase2_swarm_demo.rs` | Agent E | TBD |
| **Integration Test Suite** | All crates, tests/ | All | TBD |

---

## Parallel Execution Strategy

**Optimal:** Spawn 4 parallel agents (one per task):

```
Agent B (Week 4):    Rapid-MLX provisioning + benchmarking
Agent C (Week 5):    Chaos Petri design + implementation
Agent D (Week 5):    Sneakernet ingress gate
Agent E (Week 6):    Swarm demo integration
```

**Dependencies:**
- B must complete before C (need working cluster for chaos testing)
- D is independent (security gate, no runtime deps)
- E waits for B + C (needs both cluster + chaos framework)

**Critical Path:** B → C → E (weeks 4 → 5 → 6)

---

## Go/No-Go Gate (End of Week 6)

**Approval Criteria:**
- ✅ All 5 Mac Studio nodes operational (verified by Agent B)
- ✅ Chaos Petri passes all 12 failure scenarios (verified by Agent C)
- ✅ Sneakernet transfer completed securely (verified by Agent D)
- ✅ Live swarm demo runs without errors (verified by Agent E)
- ✅ No data loss or corruption under failure injection

**Decision:** Ready for Phase 3 or pause for investor demo?

---

**Prepared by:** Sovereign Architect  
**Status:** Ready for Phase 2 execution  
**Next Review:** Start of Week 4 (hardware delivery)


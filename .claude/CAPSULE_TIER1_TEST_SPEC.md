# CAPSULE Tier 1 Cryptographic Integrity — Test Specification

## Overview

This document describes the comprehensive test suite for CAPSULE's Tier 1 cryptographic integrity layer. The test suite follows **Test-Driven Development (TDD)** principles: all tests are written to FAIL initially, establishing the red phase. Implementation will follow to achieve the green phase.

**Test File:** `.claude/capsule/tests/test_tier1_cryptographic_integrity.py`  
**Fixtures File:** `.claude/capsule/tests/conftest.py`  
**Status:** 0/8 PASS (all tests intentionally failing)

---

## Test Categories and Specifications

### 1. Merkle Root Initialization

#### Test: `test_merkle_root_initialization()`

**Purpose:** Verify capsule engine initializes with None merkle_root.

**Rationale:**
- Fresh capsule has no mutations
- Merkle root serves as identity element for chain of hashes
- None represents uninitialized state

**Expected Behavior:**
```python
capsule_engine = CapsuleEngineMock()
assert capsule_engine.merkle_root is None
```

**Implementation Requirements:**
- CapsuleEngine constructor initializes `merkle_root = None`
- No automatic root generation on init

**Status:** FAIL (red phase)

---

### 2. Merkle Root Evolution

#### Test: `test_merkle_root_updates_on_mutation()`

**Purpose:** Verify that after mutation, merkle_root is SHA256(old || new_hash).

**Specification:**

```
old_root = previous merkle_root (or empty bytes if None)
new_hash = SHA256(payload || signature)
new_root = SHA256(old_root || new_hash)
```

**Expected Behavior:**
- `mutate("SET", {"key": "value"})` returns hex-encoded merkle_root
- Return value is 64-character hex string (SHA256 digest)
- Merkle root changes with each mutation

**Implementation Requirements:**
- `CapsuleEngine.mutate(operation, data)` method
- `CapsuleEngine._compute_merkle_root(old_root, payload, signature)` method
- Signature generation via `CapsuleEngine._sign_mutation(payload)`
- State update based on operation type

**Status:** FAIL (red phase)

#### Test: `test_merkle_root_evolves_monotonically()`

**Purpose:** Verify that multiple mutations produce different merkle roots.

**Specification:**
- Each mutation generates unique payload
- Each unique payload + signature = unique inner hash
- Unique inner hash + old root = unique outer hash
- Merkle roots form a chain: cannot repeat

**Expected Behavior:**
```python
root1 = engine.mutate("SET", {"key1": "value1"})
root2 = engine.mutate("SET", {"key2": "value2"})
root3 = engine.mutate("DELETE", {"key1"})

assert root1 != root2 != root3
assert len({root1, root2, root3}) == 3
```

**Implementation Requirements:**
- Mutations must be path-dependent (each depends on previous merkle_root)
- Internal mutation counter or unique identifiers
- Deterministic signing (same payload → same signature)

**Status:** FAIL (red phase)

---

### 3. Ed25519 Key Generation

#### Test: `test_ed25519_key_generation()`

**Purpose:** Verify capsule engine generates valid Ed25519 keypair on init.

**Specification:**

| Requirement | Spec |
|---|---|
| Public key size | 32 bytes |
| Private key size | 32 bytes |
| Key format | bytes (binary) |
| Generation time | During `__init__` |
| Library | `ed25519` or `cryptography` |

**Expected Behavior:**
```python
engine = CapsuleEngineMock()
assert len(engine.keypair.public_key_bytes) == 32
assert len(engine.keypair.private_key_bytes) == 32
assert isinstance(engine.keypair.public_key_bytes, bytes)
```

**Implementation Requirements:**
- `CapsuleEngine.__init__()` calls keypair generation
- `Ed25519TestKeyPair` stores public and private keys as bytes
- Keys are cryptographically random (or deterministic for testing)

**Status:** FAIL (red phase)

---

### 4. Signature Generation

#### Test: `test_sign_mutation_produces_signature()`

**Purpose:** Verify `_sign_mutation()` returns valid Ed25519 signature.

**Specification:**

| Property | Spec |
|---|---|
| Input | bytes (payload) |
| Output | bytes (signature) |
| Output length | 64 bytes (Ed25519 standard) |
| Determinism | Deterministic: same payload → same signature |
| Uniqueness | Different payloads → different signatures |

**Expected Behavior:**
```python
payload = b"test_payload"
sig1 = engine._sign_mutation(payload)
sig2 = engine._sign_mutation(payload)

assert len(sig1) == 64
assert sig1 == sig2  # Deterministic
assert engine._sign_mutation(b"other") != sig1
```

**Implementation Requirements:**
- `CapsuleEngine._sign_mutation(payload: bytes) -> bytes`
- Uses keypair's private key to sign
- Returns 64-byte Ed25519 signature
- Deterministic signing (use SHA256(private_key || payload) as test implementation)

**Status:** FAIL (red phase)

---

### 5. Signature Verification

#### Test: `test_signature_verifies_with_public_key()`

**Purpose:** Verify signature can be verified against public key.

**Specification:**

| Scenario | Result |
|---|---|
| Valid signature + correct payload | ✓ PASS |
| Valid signature + modified payload | ✗ FAIL |
| Invalid/random signature + correct payload | ✗ FAIL |
| Corrupted signature + correct payload | ✗ FAIL |

**Expected Behavior:**
```python
payload = b"test_payload"
sig = engine._sign_mutation(payload)

assert engine.keypair.verify(payload, sig) == True
assert engine.keypair.verify(payload + b"_modified", sig) == False
assert engine.keypair.verify(payload, b'\x00' * 64) == False
```

**Implementation Requirements:**
- `Ed25519TestKeyPair.verify(message: bytes, signature: bytes) -> bool`
- Uses public key to verify signature
- Returns boolean
- Strict verification: any modification fails

**Status:** FAIL (red phase)

---

### 6. Mutation Audit Trail

#### Test: `test_mutation_audit_trail_logged()`

**Purpose:** Verify each mutation creates audit trail entry with required metadata.

**Specification:**

**Audit Trail Entry Schema:**
```python
{
    "operation": str,           # "SET", "DELETE", etc.
    "capsule_id": str,          # Capsule identifier
    "timestamp": str,           # ISO 8601 datetime
    "signature": str,           # Hex-encoded 64-byte signature (128 chars)
    "merkle_hash": str,         # Hex-encoded SHA256 (64 chars)
    "payload": str              # (Optional) Hex-encoded mutation payload
}
```

**Expected Behavior:**
```python
engine = CapsuleEngineMock()
engine.mutate("SET", {"key1": "value1"})
engine.mutate("SET", {"key2": "value2"})
engine.mutate("DELETE", {"key1"})

assert len(engine.audit_trail) == 3

for entry in engine.audit_trail:
    assert "operation" in entry
    assert "timestamp" in entry
    assert "signature" in entry
    assert "merkle_hash" in entry
    assert len(entry["signature"]) == 128  # 64 bytes in hex
    assert len(entry["merkle_hash"]) == 64  # 32 bytes in hex
    # ISO 8601 timestamp validation
    datetime.fromisoformat(entry["timestamp"])
```

**Implementation Requirements:**
- `CapsuleEngine.audit_trail` is a list initialized as empty
- Each `mutate()` call appends entry to audit trail
- Timestamp is generated at mutation time (UTC)
- Signature is hex-encoded from `_sign_mutation()`
- Merkle hash is the updated `merkle_root`

**Status:** FAIL (red phase)

---

### 7. Monotonic Merkle Root Evolution

**Purpose:** Implicitly tested in `test_merkle_root_evolves_monotonically()`

Validates that the chain of Merkle roots is deterministic and path-dependent, enabling tamper detection.

---

### 8. Tamper Detection

#### Test: `test_tamper_detection_merkle_mismatch()`

**Purpose:** Verify corrupting state invalidates merkle_root verification.

**Specification:**

**Merkle Root Verification Algorithm:**
```
1. Start with computed_root = None
2. For each entry in audit_trail:
     inner_hash = SHA256(payload || signature)
     computed_root = SHA256(old_computed_root || inner_hash)
3. Return (computed_root == engine.merkle_root)
```

**Expected Behavior:**
```python
engine.mutate("SET", {"key1": "value1"})
engine.mutate("SET", {"key2": "value2"})

# Before tampering
assert engine.verify_merkle_root() == True

# After tampering
engine.corrupt_merkle_root()
assert engine.verify_merkle_root() == False
```

**Implementation Requirements:**
- `CapsuleEngine.verify_merkle_root() -> bool`
- Reconstructs merkle_root from audit trail
- Returns True if reconstructed == stored merkle_root
- Returns False if any mismatch or corruption detected

**Status:** FAIL (red phase)

---

## Test Fixtures and Utilities

### Fixture: `keypair`

Provides an `Ed25519TestKeyPair` instance.

```python
@pytest.fixture
def keypair() -> Ed25519TestKeyPair:
    return Ed25519TestKeyPair()
```

**Properties:**
- `public_key_hex`: Hex-encoded public key (64 chars)
- `public_key_bytes`: Public key as 32 bytes
- `private_key_hex`: Hex-encoded private key (96 chars for test)
- `private_key_bytes`: Private key as 48 bytes (test) or 32 bytes (production)
- `sign(message: bytes) -> bytes`: Sign message
- `verify(message: bytes, signature: bytes) -> bool`: Verify signature

### Fixture: `capsule_engine`

Provides a fresh `CapsuleEngineMock` instance.

```python
@pytest.fixture
def capsule_engine() -> CapsuleEngineMock:
    return CapsuleEngineMock()
```

**Initial State:**
- `capsule_id = "test-capsule-001"`
- `state = {}`
- `merkle_root = None`
- `audit_trail = []`
- `keypair = Ed25519TestKeyPair()`

### Fixture: `capsule_engine_with_mutations`

Provides a `CapsuleEngineMock` with 3 pre-applied mutations.

```python
@pytest.fixture
def capsule_engine_with_mutations() -> CapsuleEngineMock:
    engine = CapsuleEngineMock()
    engine.mutate("SET", {"key1": "value1"})
    engine.mutate("SET", {"key2": "value2"})
    engine.mutate("SET", {"key3": "value3"})
    return engine
```

### Fixture: `sample_payload`

Provides test payload: `b"test_payload_data_for_signing"`

### Fixture: `sample_signature`

Provides valid signature for `sample_payload`.

---

## Running the Tests

### Prerequisites
```bash
pip install pytest
pip install cryptography  # For real Ed25519 (future)
```

### Run All Tests
```bash
pytest .claude/capsule/tests/test_tier1_cryptographic_integrity.py -v
```

### Run Specific Test Class
```bash
pytest .claude/capsule/tests/test_tier1_cryptographic_integrity.py::TestMerkleRootInitialization -v
```

### Run with Coverage
```bash
pytest .claude/capsule/tests/ --cov=.claude/capsule --cov-report=html
```

---

## Expected Test Results (Red Phase)

```
test_merkle_root_initialization FAIL
test_merkle_root_updates_on_mutation FAIL
test_merkle_root_evolves_monotonically FAIL
test_ed25519_key_generation FAIL
test_sign_mutation_produces_signature FAIL
test_signature_verifies_with_public_key FAIL
test_mutation_audit_trail_logged FAIL
test_tamper_detection_merkle_mismatch FAIL

============ 0 passed, 8 failed in X.XXs ============
```

---

## Implementation Checklist

To transition from RED to GREEN phase, implement:

- [ ] `CapsuleEngine.__init__()` — Initialize merkle_root = None, create keypair
- [ ] `CapsuleEngine._sign_mutation(payload: bytes) -> bytes` — Sign using keypair
- [ ] `CapsuleEngine._compute_merkle_root(old_root, payload, signature) -> str` — SHA256 chain
- [ ] `CapsuleEngine.mutate(operation: str, data: Dict) -> str` — Apply mutation and update merkle
- [ ] `CapsuleEngine.verify_merkle_root() -> bool` — Reconstruct and verify
- [ ] `Ed25519TestKeyPair.sign(message: bytes) -> bytes` — Generate signature
- [ ] `Ed25519TestKeyPair.verify(message: bytes, signature: bytes) -> bool` — Verify signature
- [ ] Audit trail logging in `mutate()` method

---

## Cryptographic Properties

### Merkle Root Chain

The Merkle root chain guarantees:

1. **Integrity:** Any change to past mutations is detected
2. **Authenticity:** Signatures prove mutations came from capsule owner
3. **Non-repudiation:** Audit trail with signatures proves history
4. **Immutability:** Audit trail is append-only

### Hash Function: SHA256

```
inner_hash = SHA256(payload || signature)
outer_hash = SHA256(old_root || inner_hash)
```

**Properties:**
- Avalanche effect: 1-bit change → completely different hash
- Deterministic: same input → same output
- One-way: cannot reverse hash to get input
- Collision-resistant: extremely unlikely to find two inputs with same hash

### Signature Algorithm: Ed25519

**Properties:**
- 256-bit security level
- 64-byte signature size
- Deterministic signing (no random nonce)
- Fast verification
- Strong against side-channel attacks

---

## Test Coverage Matrix

| Feature | Tests | Status |
|---|---|---|
| Merkle root initialization | 1 | FAIL |
| Merkle root evolution | 2 | FAIL |
| Ed25519 key generation | 1 | FAIL |
| Signature generation | 1 | FAIL |
| Signature verification | 1 | FAIL |
| Audit trail logging | 1 | FAIL |
| Tamper detection | 1 | FAIL |
| **Total** | **8** | **0/8 PASS** |

---

## Notes for Implementers

1. **Test Determinism:** Keypair is hardcoded for reproducibility. Production should use real key generation.
2. **Payload Format:** Tests use JSON representation (`str(data)`). Production may use protobuf or msgpack.
3. **Timestamp Precision:** ISO 8601 format allows for different precisions (microseconds, seconds). Be consistent.
4. **Audit Trail Immutability:** Once written, audit entries should not be modified. Consider storing as append-only log.
5. **Performance:** SHA256 is O(n) in payload size. For large mutations, consider streaming hash.

---

## References

- [Ed25519 RFC 8032](https://tools.ietf.org/html/rfc8032)
- [SHA256 NIST](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [Merkle Tree Wikipedia](https://en.wikipedia.org/wiki/Merkle_tree)
- [TDD by Example - Kent Beck](https://www.oreilly.com/library/view/test-driven-development/0321146530/)

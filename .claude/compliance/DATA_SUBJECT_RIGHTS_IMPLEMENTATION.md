# Data Subject Rights API Implementation Guide

**Version:** 1.0  
**Date:** July 16, 2026  
**Status:** TECHNICAL-READY (spec + implementation checklist)  
**Quality Bar:** 8/10 (clear API contracts, testable)

---

## Overview

This guide provides step-by-step implementation instructions for GDPR Article 12–22 data subject rights via REST API.

**Five Core Rights:**
1. **Right of Access (Article 15)** — Retrieve all personal data held
2. **Right to Erasure (Article 17)** — Delete personal data (right to be forgotten)
3. **Right to Rectification (Article 16)** — Correct inaccurate data
4. **Right to Portability (Article 20)** — Export data in portable format
5. **Right to Object (Article 21)** — Object to processing

---

## 1. API Architecture

### 1.1 Base Endpoint

**Production:** `https://api.sovereignnexus.io/api/v1/data`

**Authentication:**
- JWT token (issued by SISS after successful authentication)
- OR email verification code + one-time token
- Rate limit: 100 requests/min per authenticated user

### 1.2 Request/Response Format

**Standard Request:**
```http
POST /api/v1/data/{endpoint}
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-Request-ID: {uuid}
X-Idempotency-Key: {uuid}

{
  "subject_id": "agent-uuid",
  "reason": "user_request",
  "additional_context": "optional"
}
```

**Standard Response (Success):**
```json
{
  "request_id": "req-uuid",
  "status": "success",
  "data": {...},
  "timestamp": "2026-07-16T10:00:00Z",
  "processing_time_ms": 125
}
```

**Standard Response (Error):**
```json
{
  "request_id": "req-uuid",
  "status": "error",
  "error_code": "SUBJECT_NOT_FOUND",
  "error_message": "No subject with ID agent-uuid",
  "timestamp": "2026-07-16T10:00:00Z"
}
```

---

## 2. Right of Access (SAR) Implementation

### 2.1 API Endpoint

```http
POST /api/v1/data/subject-access-request
Authorization: Bearer {token}
Content-Type: application/json

{
  "subject_id": "agent-uuid",
  "format": "json",           # or "xml", "csv"
  "include": [
    "attestations",
    "decisions",
    "audit_trail",
    "metadata"
  ]
}

Response (202 Accepted):
{
  "request_id": "sar-req-001",
  "subject_id": "agent-uuid",
  "status": "processing",
  "estimated_completion": "2026-07-23T10:00:00Z",
  "download_url": "https://api.sovereignnexus.io/downloads/sar-req-001",
  "download_expires_at": "2026-08-23T10:00:00Z"
}
```

### 2.2 Database Schema

**Create SAR Request Tracking:**

```sql
CREATE TABLE gdpr_sar_requests (
    id UUID PRIMARY KEY,
    subject_id UUID NOT NULL,
    requested_by_email VARCHAR(255),
    requested_at TIMESTAMP NOT NULL,
    format VARCHAR(10),  -- json, xml, csv
    status VARCHAR(20),  -- processing, completed, failed
    data_categories JSONB,
    file_path VARCHAR(512),  -- Path to generated file
    file_encrypted BOOLEAN,
    encryption_algorithm VARCHAR(50),  -- aes-256-gcm
    download_token UUID,
    download_expires_at TIMESTAMP,
    completion_estimated_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    audit_trail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sar_subject ON gdpr_sar_requests(subject_id);
CREATE INDEX idx_sar_status ON gdpr_sar_requests(status);
CREATE INDEX idx_sar_requested_at ON gdpr_sar_requests(requested_at);
```

### 2.3 Implementation Steps

**Step 1: Authentication & Authorization**

```python
@app.post("/api/v1/data/subject-access-request")
def subject_access_request(request: SARRequest, token: str = Header(...)):
    # Verify JWT token
    user = verify_jwt_token(token)
    
    # Verify subject_id matches authenticated user OR user is DPO
    if user.subject_id != request.subject_id and user.role != "dpo":
        return error_response("UNAUTHORIZED", "Cannot access other subject's data")
    
    # Log request
    log_audit("SAR_REQUESTED", subject_id=request.subject_id, requested_by=user.id)
    
    return accept_sar_request(request)
```

**Step 2: SAR Request Creation**

```python
def accept_sar_request(request: SARRequest):
    # Create request record
    sar_id = uuid.uuid4()
    db.execute("""
        INSERT INTO gdpr_sar_requests
        (id, subject_id, requested_by_email, requested_at, format, status, data_categories)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        sar_id,
        request.subject_id,
        request.requested_email,
        datetime.utcnow(),
        request.format,
        "processing",
        json.dumps(request.include)
    ))
    
    # Queue background job to compile data
    queue_sar_job(sar_id, request.subject_id, request.format)
    
    return {
        "request_id": str(sar_id),
        "status": "processing",
        "estimated_completion": (datetime.utcnow() + timedelta(days=30)).isoformat()
    }
```

**Step 3: Background Job — Data Compilation (30-day SLA)**

```python
@background_job
def compile_sar_data(sar_id: str, subject_id: str, format: str):
    try:
        data = {
            "subject": get_subject_info(subject_id),
            "attestations": get_attestations(subject_id),
            "decisions": get_governance_decisions(subject_id),
            "audit_trail": get_audit_entries(subject_id),
            "metadata": get_session_metadata(subject_id)
        }
        
        # Anonymize references to other subjects in audit trail
        data["audit_trail"] = anonymize_references(data["audit_trail"])
        
        # Export to requested format
        if format == "json":
            exported_data = json.dumps(data, indent=2)
        elif format == "xml":
            exported_data = to_xml(data)
        elif format == "csv":
            exported_data = to_csv(data)
        
        # Encrypt with subject's public key (if provided) or system key
        encrypted_data = encrypt_aes256(exported_data)
        
        # Store in secure location
        file_path = f"/secure/sar/{sar_id}/data.{format}.enc"
        store_securely(file_path, encrypted_data)
        
        # Generate download token
        download_token = generate_secure_token(sar_id)
        
        # Update SAR request status
        db.execute("""
            UPDATE gdpr_sar_requests
            SET status = %s, file_path = %s, download_token = %s,
                download_expires_at = %s, completed_at = %s
            WHERE id = %s
        """, (
            "completed",
            file_path,
            download_token,
            datetime.utcnow() + timedelta(days=30),
            datetime.utcnow(),
            sar_id
        ))
        
        # Email subject with download link
        send_sar_completion_email(subject_id, download_token)
        log_audit("SAR_COMPLETED", subject_id=subject_id, sar_id=sar_id)
        
    except Exception as e:
        log_error(f"SAR compilation failed: {e}")
        db.execute("""
            UPDATE gdpr_sar_requests
            SET status = %s, error_message = %s
            WHERE id = %s
        """, ("failed", str(e), sar_id))
        send_sar_error_email(subject_id, sar_id)
```

**Step 4: Download Endpoint**

```python
@app.get("/downloads/{download_token}")
def download_sar_data(download_token: str):
    # Lookup SAR request by token
    sar = db.query("""
        SELECT * FROM gdpr_sar_requests WHERE download_token = %s
    """, (download_token,))
    
    if not sar or sar.download_expires_at < datetime.utcnow():
        return error_response("DOWNLOAD_EXPIRED", "Link expired or invalid")
    
    # Log download
    log_audit("SAR_DOWNLOADED", sar_id=sar.id, download_token=download_token)
    
    # Return encrypted file with expiry header
    return send_file(
        sar.file_path,
        as_attachment=True,
        download_name=f"data-export-{sar.subject_id}.enc",
        headers={"X-Expires": sar.download_expires_at.isoformat()}
    )
```

### 2.4 Testing Checklist

- [ ] SAR request accepted (202 status)
- [ ] Request ID returned + tracked
- [ ] Estimated completion date = 30 days from request
- [ ] Background job queued successfully
- [ ] Data compiled within 30 days
- [ ] Export format valid (JSON schema, XML validation, CSV headers)
- [ ] Other subjects' references anonymized
- [ ] Encryption applied (AES-256)
- [ ] Download link generated + expires after 30 days
- [ ] Email sent to subject with download instructions
- [ ] Audit trail logged (request created, data compiled, download)

---

## 3. Right to Erasure Implementation

### 3.1 API Endpoint

```http
DELETE /api/v1/data/{subject_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "user_request",  # or "contract_termination", "no_longer_necessary"
  "permanent": true
}

Response (202 Accepted):
{
  "deletion_request_id": "del-req-001",
  "subject_id": "agent-uuid",
  "status": "initiated",
  "grace_period_until": "2026-08-16T23:59:59Z",
  "message": "Deletion will be irreversible after grace period"
}
```

### 3.2 Database Schema

```sql
CREATE TABLE gdpr_deletion_requests (
    id UUID PRIMARY KEY,
    subject_id UUID NOT NULL,
    requested_by_email VARCHAR(255),
    requested_at TIMESTAMP NOT NULL,
    reason VARCHAR(50),
    grace_period_until TIMESTAMP,
    status VARCHAR(20),  -- initiated, grace_period, completed
    permanent BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    executed_at TIMESTAMP,
    audit_trail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_deletion_subject ON gdpr_deletion_requests(subject_id);
CREATE INDEX idx_deletion_status ON gdpr_deletion_requests(status);
```

### 3.3 Implementation Steps

**Step 1: Initiate Deletion (30-day grace period)**

```python
@app.delete("/api/v1/data/{subject_id}")
def initiate_deletion(subject_id: str, request: DeletionRequest, token: str = Header(...)):
    user = verify_jwt_token(token)
    
    # Verify authorization
    if user.subject_id != subject_id and user.role != "dpo":
        return error_response("UNAUTHORIZED")
    
    # Check if deletion already in progress
    existing = db.query("""
        SELECT * FROM gdpr_deletion_requests
        WHERE subject_id = %s AND status != 'completed'
    """, (subject_id,))
    
    if existing:
        return error_response("DELETION_ALREADY_PENDING")
    
    # Create deletion request
    del_id = uuid.uuid4()
    grace_period_until = datetime.utcnow() + timedelta(days=30)
    
    db.execute("""
        INSERT INTO gdpr_deletion_requests
        (id, subject_id, requested_by_email, requested_at, reason, grace_period_until, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        del_id, subject_id, user.email, datetime.utcnow(),
        request.reason, grace_period_until, "initiated"
    ))
    
    # Schedule automatic deletion after grace period
    schedule_deletion_job(del_id, subject_id, grace_period_until)
    
    # Send confirmation email (allow cancellation)
    send_deletion_confirmation_email(subject_id, del_id)
    
    log_audit("DELETION_INITIATED", subject_id=subject_id, del_id=del_id)
    
    return {
        "deletion_request_id": str(del_id),
        "status": "initiated",
        "grace_period_until": grace_period_until.isoformat()
    }
```

**Step 2: Cancellation During Grace Period**

```python
@app.post("/api/v1/data/{subject_id}/deletion/{del_id}/cancel")
def cancel_deletion(subject_id: str, del_id: str, token: str = Header(...)):
    user = verify_jwt_token(token)
    
    # Verify authorization
    if user.subject_id != subject_id:
        return error_response("UNAUTHORIZED")
    
    # Lookup deletion request
    deletion = db.query("""
        SELECT * FROM gdpr_deletion_requests WHERE id = %s AND subject_id = %s
    """, (del_id, subject_id))
    
    if not deletion or deletion.grace_period_until < datetime.utcnow():
        return error_response("CANNOT_CANCEL", "Grace period expired")
    
    # Cancel deletion
    db.execute("""
        UPDATE gdpr_deletion_requests
        SET status = %s, cancelled_at = %s WHERE id = %s
    """, ("cancelled", datetime.utcnow(), del_id))
    
    log_audit("DELETION_CANCELLED", subject_id=subject_id, del_id=del_id)
    
    return {"status": "cancelled", "message": "Deletion request cancelled"}
```

**Step 3: Execute Deletion (Automatic, after grace period)**

```python
@background_job
def execute_deletion(del_id: str, subject_id: str):
    try:
        # 1. Mark deletion as in-progress
        db.execute("""
            UPDATE gdpr_deletion_requests
            SET status = %s WHERE id = %s
        """, ("executing", del_id))
        
        # 2. Revoke all sessions (transitive revocation via SISS)
        revoke_subject_sessions(subject_id)
        
        # 3. Anonymize audit trail (φ-pruning)
        # Remove subject references from Merkle-DAG decision nodes
        prune_merkle_dag(subject_id)
        
        # 4. Delete live data (attestations, session metadata)
        db.execute("""
            DELETE FROM attestations WHERE agent_id = %s
        """, (subject_id,))
        
        db.execute("""
            DELETE FROM session_metadata WHERE agent_id = %s
        """, (subject_id,))
        
        # 5. Anonymize linked records (delegation edges, consent)
        db.execute("""
            UPDATE delegation_edges
            SET source_persona_id = %s WHERE source_persona_id = %s
        """, (uuid.uuid4(), subject_id))
        
        # 6. Mark deletion as complete
        db.execute("""
            UPDATE gdpr_deletion_requests
            SET status = %s, executed_at = %s WHERE id = %s
        """, ("completed", datetime.utcnow(), del_id))
        
        # 7. Log deletion event
        log_audit("DELETION_EXECUTED", subject_id=subject_id, del_id=del_id)
        
        # 8. Send confirmation email
        send_deletion_confirmation_email(subject_id)
        
    except Exception as e:
        log_error(f"Deletion failed: {e}")
        # Manual DPO intervention required
        escalate_to_dpo(del_id, f"Deletion execution failed: {e}")
```

### 3.4 Testing Checklist

- [ ] Deletion request accepted (202 status)
- [ ] 30-day grace period calculated correctly
- [ ] Cancellation link works during grace period
- [ ] Cancellation prevented after grace period
- [ ] Deletion scheduled for execution (after grace period)
- [ ] Sessions revoked (SISS transitive revocation)
- [ ] Attestations deleted from live database
- [ ] Audit trail anonymized (φ-pruning completes)
- [ ] Merkle-DAG integrity verified (hash recomputation)
- [ ] Confirmation email sent
- [ ] Deletion audit trail immutable

---

## 4. Right to Rectification Implementation

```http
PATCH /api/v1/data/{subject_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "corrections": [
    {
      "field": "agent_name",
      "current_value": "Agent-Alpha",
      "corrected_value": "Agent-Alpha-v2",
      "reason": "Agent renamed"
    }
  ]
}

Response (200 OK):
{
  "subject_id": "agent-uuid",
  "corrections_applied": 1,
  "corrected_at": "2026-07-16T10:05:00Z",
  "audit_entry_id": "rect-001"
}
```

**Implementation (Abbreviated):**
1. Authenticate + authorize (subject or DPO only)
2. Validate correctable fields (name, email, contact info only)
3. Apply corrections to live database
4. Log before/after values in audit trail
5. Invalidate caches (refresh tokens if identity changed)
6. Return correction confirmation

---

## 5. Right to Portability Implementation

```http
GET /api/v1/data/{subject_id}/portable
Authorization: Bearer {token}

Response (200 OK):
{
  "portable_data": {
    "subject": {...},
    "attestations": [...],
    "decisions": [...]
  },
  "format": "application/json",
  "export_date": "2026-07-16T10:00:00Z"
}
```

**Implementation (Abbreviated):**
1. Authenticate + authorize
2. Compile all personal data in portable format (JSON/XML)
3. Ensure structure is machine-readable (no PDFs, images)
4. Include metadata (timestamps, issuer info, data categories)
5. Exclude other data subjects' references
6. Return immediately (no background job needed)

---

## 6. Right to Object Implementation

```http
POST /api/v1/data/{subject_id}/objection
Authorization: Bearer {token}
Content-Type: application/json

{
  "objection_type": "processing",
  "grounds": "agent_opposes_governance_processing",
  "details": "Request review of policy X"
}

Response (202 Accepted):
{
  "objection_id": "obj-001",
  "status": "pending_review",
  "next_review_date": "2026-08-16"
}
```

**Implementation (Abbreviated):**
1. Log objection in audit trail
2. Escalate to DPO within 24 hours
3. DPO reviews + decides within 14 days
4. If cease processing: Revoke session + anonymize data
5. Send decision to subject

---

## 7. Compliance Verification

### 7.1 Quality Assurance Checklist

- [ ] All 5 endpoints tested + working
- [ ] Authentication + authorization enforced
- [ ] 30-day SLA met for SARs
- [ ] Encryption applied (AES-256)
- [ ] Audit trail immutable (every request logged)
- [ ] Error handling graceful (no sensitive data in error messages)
- [ ] Rate limiting enforced (100 requests/min per user)
- [ ] Data anonymization verified (no subject reference leakage)
- [ ] Email notifications sent correctly
- [ ] Download links expire after 30 days
- [ ] Grace period enforcement (30-day deletion window)

### 7.2 Load Testing

```bash
# Simulate 100 concurrent SARs
artillery run data-subject-rights-load-test.yml

# Expected: API handles 10+ concurrent requests without degradation
# Response time <500ms for SAR initiation
# Background job queue <1000 ms for processing initiation
```

### 7.3 Security Testing

- [ ] Injection attacks blocked (SQL injection, command injection)
- [ ] CSRF protection enabled (CSRF token validation)
- [ ] Leaked data prevention (no sensitive fields in logs)
- [ ] Authorization bypass prevention (RBAC verified)
- [ ] Encryption verified (AES-256 checksum, key rotation)

---

## 8. Deployment Checklist

- [ ] Database migrations applied
- [ ] API endpoints deployed to staging
- [ ] Integration tests passed
- [ ] Load tests successful
- [ ] Security review approved
- [ ] DPO sign-off obtained
- [ ] Documentation updated
- [ ] Support team trained
- [ ] Email templates configured
- [ ] Monitoring + alerting configured
- [ ] Deployment to production scheduled

---

**Implementation Timeline:** Aug 1–Aug 31, 2026  
**Testing Timeline:** Aug 15–Aug 31, 2026  
**Deployment:** Sep 1, 2026 (EU AI Act enforcement date)  
**SLA:** 30-day turnaround for all subject rights requests

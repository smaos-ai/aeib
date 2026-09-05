-- Phase 38: RCE Checkpoint Durability Layer
--
-- Persistent storage for paused workflow state with checkpoint integrity
-- and append-only audit trail for human-in-the-loop decisions.

-- Durable workflow state and checkpoint storage
CREATE TABLE rce_checkpoints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL,
    step_index      INTEGER NOT NULL,
    state           JSONB NOT NULL,           -- serialized ResumableCognitiveExecution
    checksum        TEXT NOT NULL,            -- SHA-256 of state bytes
    version         INTEGER NOT NULL DEFAULT 1,
    reason          TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'High',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_rce_checkpoints_workflow UNIQUE (workflow_id)
);

-- Append-only audit trail for human decisions
CREATE TABLE rce_audit_trail (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID NOT NULL,
    event_type      TEXT NOT NULL,
    decision        TEXT,                     -- Approve | Reject | Modify | NULL
    decided_by      TEXT,
    reason          TEXT,
    details         JSONB NOT NULL DEFAULT '{}',
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for fast lookups
CREATE INDEX idx_rce_checkpoints_workflow_id ON rce_checkpoints(workflow_id);
CREATE INDEX idx_rce_audit_trail_workflow_id ON rce_audit_trail(workflow_id);
CREATE INDEX idx_rce_audit_trail_occurred_at ON rce_audit_trail(occurred_at DESC);

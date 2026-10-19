-- src/storage/postgres_bitemporal_outbox.sql
-- =============================================================================
-- AEIB PostgreSQL Bitemporal Outbox & Atomic TCC Reservation Schema (Pillars 1 & 2)
--
-- Implements:
--   1. Pessimistic TCC (Try-Confirm-Cancel) with row-level SELECT ... FOR UPDATE NOWAIT
--      to eliminate concurrent subagent double-spending.
--   2. Bitemporal tracking (valid_time_range and system_time_range tstzrange).
--   3. Transactional Outbox pattern with Debezium CDC publication table.
--   4. Optimistic Concurrency Control (OCC) with version and CAS invariants.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- 1. Workflow Budget Table (Pessimistic Escrow Root)
CREATE TABLE IF NOT EXISTS workflow_budget (
    workflow_id VARCHAR(128) PRIMARY KEY,
    budget_minor BIGINT NOT NULL CHECK (budget_minor >= 0),
    reserved_minor BIGINT NOT NULL DEFAULT 0 CHECK (reserved_minor >= 0),
    confirmed_minor BIGINT NOT NULL DEFAULT 0 CHECK (confirmed_minor >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_budget_ceiling CHECK (reserved_minor + confirmed_minor <= budget_minor)
);

-- 2. Bitemporal TCC Outbox Journal
CREATE TABLE IF NOT EXISTS tcc_outbox_journal (
    operation_id VARCHAR(128) PRIMARY KEY,
    workflow_id VARCHAR(128) NOT NULL REFERENCES workflow_budget(workflow_id),
    subagent_id VARCHAR(128) NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
    compensatable BOOLEAN NOT NULL DEFAULT TRUE,
    tcc_state VARCHAR(32) NOT NULL CHECK (
        tcc_state IN ('TRY_RESERVED', 'CONFIRMED', 'CANCELLED', 'EFFECT_INDETERMINATE', 'RESOLVED_REFUTED')
    ),
    dispatch_ts BIGINT NOT NULL,
    visibility_bound_sec INT NOT NULL DEFAULT 60,
    action_caid VARCHAR(128) NOT NULL,
    valid_time_range TSTZRANGE NOT NULL DEFAULT TSTZRANGE(NOW(), 'infinity'),
    system_time_range TSTZRANGE NOT NULL DEFAULT TSTZRANGE(NOW(), 'infinity')
);

CREATE INDEX IF NOT EXISTS idx_tcc_workflow_state ON tcc_outbox_journal(workflow_id, tcc_state);
CREATE INDEX IF NOT EXISTS idx_tcc_action_caid ON tcc_outbox_journal(action_caid);

-- 3. Optimistic Concurrency Control (OCC) Entity State Table
CREATE TABLE IF NOT EXISTS occ_entity_state (
    entity_id VARCHAR(128) PRIMARY KEY,
    version BIGINT NOT NULL DEFAULT 1,
    policy_epoch BIGINT NOT NULL,
    context_manifest_hash VARCHAR(128) NOT NULL,
    state_payload_jcs TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Transactional Outbox for Debezium CDC Stream
CREATE TABLE IF NOT EXISTS tcc_cdc_outbox_events (
    event_id BIGSERIAL PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL DEFAULT 'AEIB_TCC_OUTBOX',
    aggregate_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload_jcs JSONB NOT NULL,
    caid VARCHAR(128) NOT NULL,
    signature_b64 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Stored Function: Atomic TCC Try Reservation with FOR UPDATE NOWAIT
CREATE OR REPLACE FUNCTION fn_try_reserve_tcc_escrow(
    p_workflow_id VARCHAR(128),
    p_operation_id VARCHAR(128),
    p_subagent_id VARCHAR(128),
    p_amount_minor BIGINT,
    p_action_caid VARCHAR(128),
    p_dispatch_ts BIGINT,
    p_compensatable BOOLEAN DEFAULT TRUE,
    p_visibility_bound_sec INT DEFAULT 60
) RETURNS JSONB AS $$
DECLARE
    v_budget BIGINT;
    v_reserved BIGINT;
    v_confirmed BIGINT;
BEGIN
    -- Acquire exclusive row lock without waiting to fail fast on contention
    SELECT budget_minor, reserved_minor, confirmed_minor
    INTO v_budget, v_reserved, v_confirmed
    FROM workflow_budget
    WHERE workflow_id = p_workflow_id
    FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_WORKFLOW_NOT_FOUND');
    END IF;

    -- Evaluate budget ceiling under the stated model
    IF (v_reserved + v_confirmed + p_amount_minor) > v_budget THEN
        RETURN jsonb_build_object(
            'success', false,
            'status', 'HALT_BUDGET_EXCEEDED',
            'available_minor', (v_budget - (v_reserved + v_confirmed)),
            'requested_minor', p_amount_minor
        );
    END IF;

    -- Atomic reservation update
    UPDATE workflow_budget
    SET reserved_minor = reserved_minor + p_amount_minor,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id;

    -- Record in bitemporal outbox journal
    INSERT INTO tcc_outbox_journal (
        operation_id, workflow_id, subagent_id, amount_minor,
        compensatable, tcc_state, dispatch_ts, visibility_bound_sec, action_caid
    ) VALUES (
        p_operation_id, p_workflow_id, p_subagent_id, p_amount_minor,
        p_compensatable, 'TRY_RESERVED', p_dispatch_ts, p_visibility_bound_sec, p_action_caid
    );

    RETURN jsonb_build_object(
        'success', true,
        'status', 'TCC_TRY_RESERVED',
        'operation_id', p_operation_id,
        'amount_minor', p_amount_minor
    );
EXCEPTION
    WHEN lock_not_available THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_LOCK_CONTENTION_NOWAIT');
END;
$$ LANGUAGE plpgsql;

-- 6. Stored Function: Confirm TCC Reservation
CREATE OR REPLACE FUNCTION fn_confirm_tcc_escrow(
    p_workflow_id VARCHAR(128),
    p_operation_id VARCHAR(128)
) RETURNS JSONB AS $$
DECLARE
    v_amount BIGINT;
    v_state VARCHAR(32);
BEGIN
    SELECT amount_minor, tcc_state
    INTO v_amount, v_state
    FROM tcc_outbox_journal
    WHERE operation_id = p_operation_id AND workflow_id = p_workflow_id
    FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_OPERATION_NOT_FOUND');
    END IF;

    IF v_state NOT IN ('TRY_RESERVED', 'EFFECT_INDETERMINATE') THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_INVALID_STATE_FOR_CONFIRM', 'current_state', v_state);
    END IF;

    -- Lock workflow budget row
    PERFORM 1 FROM workflow_budget WHERE workflow_id = p_workflow_id FOR UPDATE NOWAIT;

    -- Transition reserved to confirmed spend
    UPDATE workflow_budget
    SET reserved_minor = reserved_minor - v_amount,
        confirmed_minor = confirmed_minor + v_amount,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id;

    UPDATE tcc_outbox_journal
    SET tcc_state = 'CONFIRMED',
        valid_time_range = TSTZRANGE(LOWER(valid_time_range), NOW())
    WHERE operation_id = p_operation_id;

    RETURN jsonb_build_object('success', true, 'status', 'TCC_CONFIRMED', 'operation_id', p_operation_id);
END;
$$ LANGUAGE plpgsql;

-- 7. Stored Function: Cancel TCC Reservation (Compensation Rollback)
CREATE OR REPLACE FUNCTION fn_cancel_tcc_escrow(
    p_workflow_id VARCHAR(128),
    p_operation_id VARCHAR(128)
) RETURNS JSONB AS $$
DECLARE
    v_amount BIGINT;
    v_state VARCHAR(32);
BEGIN
    SELECT amount_minor, tcc_state
    INTO v_amount, v_state
    FROM tcc_outbox_journal
    WHERE operation_id = p_operation_id AND workflow_id = p_workflow_id
    FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_OPERATION_NOT_FOUND');
    END IF;

    IF v_state NOT IN ('TRY_RESERVED', 'EFFECT_INDETERMINATE') THEN
        RETURN jsonb_build_object('success', false, 'status', 'HALT_INVALID_STATE_FOR_CANCEL', 'current_state', v_state);
    END IF;

    -- Lock workflow budget row
    PERFORM 1 FROM workflow_budget WHERE workflow_id = p_workflow_id FOR UPDATE NOWAIT;

    -- Release reserved spend back to available budget
    UPDATE workflow_budget
    SET reserved_minor = reserved_minor - v_amount,
        updated_at = NOW()
    WHERE workflow_id = p_workflow_id;

    UPDATE tcc_outbox_journal
    SET tcc_state = 'CANCELLED',
        valid_time_range = TSTZRANGE(LOWER(valid_time_range), NOW())
    WHERE operation_id = p_operation_id;

    RETURN jsonb_build_object('success', true, 'status', 'TCC_CANCELLED', 'operation_id', p_operation_id);
END;
$$ LANGUAGE plpgsql;

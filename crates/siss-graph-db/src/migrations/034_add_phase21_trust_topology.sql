-- Phase 21: Hybrid Trust Topology Engine
-- Directional, decay-aware, interaction-gated peer trust scoring

CREATE TABLE trust_network_edges (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_sovereign_id     UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    target_sovereign_id     UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    explicit_confidence     NUMERIC(3,2)    CHECK (explicit_confidence BETWEEN 0.00 AND 1.00),
    hybrid_trust_score      SMALLINT        NOT NULL DEFAULT 0 CHECK (hybrid_trust_score BETWEEN 0 AND 100),
    explicit_component      SMALLINT        NOT NULL DEFAULT 0,
    implicit_component      SMALLINT        NOT NULL DEFAULT 0,
    decay_component         SMALLINT        NOT NULL DEFAULT 0,
    transitive_component    SMALLINT                 CHECK (transitive_component >= 0),
    last_interaction_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    settled_invoice_count   INT             NOT NULL DEFAULT 0 CHECK (settled_invoice_count >= 0),
    is_explicit_eligible    BOOLEAN         NOT NULL DEFAULT FALSE,
    eligibility_met_at      TIMESTAMPTZ,
    voucher_count           INT             NOT NULL DEFAULT 0 CHECK (voucher_count >= 0),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_updated_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trust_edge_pair UNIQUE (source_sovereign_id, target_sovereign_id),
    CONSTRAINT check_no_self_trust CHECK (source_sovereign_id != target_sovereign_id)
);

CREATE INDEX idx_trust_edges_source ON trust_network_edges(source_sovereign_id, hybrid_trust_score DESC);
CREATE INDEX idx_trust_edges_target ON trust_network_edges(target_sovereign_id, hybrid_trust_score DESC);
CREATE INDEX idx_trust_edges_decay_sweep ON trust_network_edges(last_interaction_at ASC);
CREATE INDEX idx_trust_edges_eligible ON trust_network_edges(source_sovereign_id)
    WHERE is_explicit_eligible = TRUE AND explicit_confidence IS NULL;

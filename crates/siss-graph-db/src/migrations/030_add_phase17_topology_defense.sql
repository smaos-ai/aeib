-- Phase 17 Task 82A: Peer health scores
-- One row per sovereign; upserted by background scoring job
CREATE TABLE peer_scoring (
    sovereign_id UUID PRIMARY KEY REFERENCES sovereigns(id) ON DELETE CASCADE,
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    health_status VARCHAR(32) NOT NULL
        CHECK (health_status IN ('active', 'probation', 'quarantined', 'unknown')),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Phase 17 Task 82B: Peer clusters
-- One row per sovereign; cluster_label derived from score range
CREATE TABLE peer_clusters (
    sovereign_id UUID PRIMARY KEY REFERENCES sovereigns(id) ON DELETE CASCADE,
    cluster_label VARCHAR(32) NOT NULL
        CHECK (cluster_label IN ('clean', 'probation', 'risky')),
    score_at_assignment SMALLINT NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_clusters_label ON peer_clusters(cluster_label, assigned_at DESC);

-- Phase 17 Task 81: Peer selection preference flag
-- Opt-in preference to exclude risky (quarantined) peers from selection
ALTER TABLE sovereigns ADD COLUMN IF NOT EXISTS prefer_clean_peers BOOLEAN NOT NULL DEFAULT FALSE;

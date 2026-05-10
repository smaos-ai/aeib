-- Phase 11: Peer Discovery
-- Constitutional invariant: DISCOVERY_OPT_IN_REQUIRED

ALTER TABLE sovereigns
    ADD COLUMN is_discoverable BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN discovery_metadata JSONB,
    ADD COLUMN known_bootstrap_peers JSONB;

CREATE INDEX idx_sovereigns_discoverable ON sovereigns(id)
    WHERE is_discoverable = TRUE AND endpoint_url IS NOT NULL;

CREATE TABLE peer_announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    announcing_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    announced_to_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    announced_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    gossip_message_id UUID REFERENCES gossip_messages(id),
    announced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_peer_announcement UNIQUE (
        announcing_sovereign_id, announced_to_sovereign_id, announced_sovereign_id
    )
);

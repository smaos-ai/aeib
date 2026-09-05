-- sovereign_attributes: Store AP2 attribute values
-- (e.g., risk_class, budget, tool_access)
CREATE TABLE IF NOT EXISTS sovereign_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL,
    attribute_name TEXT NOT NULL,
    attribute_value TEXT NOT NULL,
    effective_date TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '90 days'),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_active_attribute UNIQUE (entity_id, attribute_name)
);

CREATE INDEX idx_sovereign_attributes_entity ON sovereign_attributes(entity_id);
CREATE INDEX idx_sovereign_attributes_expires ON sovereign_attributes(expires_at);

-- attribute_predicates: Define AP2 evaluation rules
-- (e.g., "if risk_class=HIGH, deny")
CREATE TABLE IF NOT EXISTS attribute_predicates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL,
    attribute_name TEXT NOT NULL,
    predicate_operator TEXT NOT NULL,
    predicate_value TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_predicate UNIQUE (entity_id, attribute_name, predicate_operator, predicate_value)
);

CREATE INDEX idx_attribute_predicates_entity ON attribute_predicates(entity_id);

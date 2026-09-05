-- SISS Knowledge Graph: Default Governance Rules
-- These are the spec-mandated invariants encoded as first-class graph objects.
-- This migration creates a function that seeds governance rules for a new tenant.

CREATE OR REPLACE FUNCTION seed_governance_rules(p_tenant_id UUID, p_system_persona_id UUID)
RETURNS void AS $$
BEGIN
    INSERT INTO governance_rules (tenant_id, name, rule_type, expression, severity, applies_to, created_by) VALUES
    (p_tenant_id, 'budget_cannot_exceed_limit', 'ap2',
     'IntentMandate.budget_spent <= IntentMandate.budget_limit',
     'critical', ARRAY['IntentMandate', 'PaymentMandate'], p_system_persona_id),

    (p_tenant_id, 'cross_tenant_edge_forbidden', 'rebac',
     'edge.source.tenant_id == edge.target.tenant_id',
     'critical', ARRAY['edges'], p_system_persona_id),

    (p_tenant_id, 'memory_gc_threshold', 'memory_lifecycle',
     'Memory.confidence_score >= 0.1 OR Memory.is_pinned == true',
     'enforced', ARRAY['memories'], p_system_persona_id),

    (p_tenant_id, 'task_fsm_valid_transitions', 'task_fsm',
     'Task.status transitions follow defined FSM',
     'enforced', ARRAY['tasks'], p_system_persona_id),

    (p_tenant_id, 'session_token_budget', 'context',
     'Session.tokens_consumed <= Session.token_budget',
     'enforced', ARRAY['sessions'], p_system_persona_id);
END;
$$ LANGUAGE plpgsql;

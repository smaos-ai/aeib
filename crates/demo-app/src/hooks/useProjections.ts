import { useEffect, useState } from 'react';
import { UUID } from 'crypto';

// Types (matching Rust data contracts)
export interface AgentAction {
  action_id: UUID;
  behavior_event_id: UUID;
  session_id: UUID;
  persona_id: UUID;
  sovereign_id: UUID;
  event_type: string;
  tier_before: number;
  tier_after: number;
  cost_incurred: number;
  lineage_safe: boolean;
  scored_at: string; // ISO DateTime
}

export interface AgentActionsState {
  actions: AgentAction[];
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
  total_count: number;
  has_more: boolean;
}

export interface Anomaly {
  anomaly_id: UUID;
  anomaly_db_id: UUID;
  sovereign_id: UUID;
  persona_id?: UUID;
  anomaly_type: string;
  severity: string;
  event_count: number;
  window_hours: number;
  evidence: Record<string, unknown>;
  detected_at: string;
  recovery_triggered: boolean;
  recovery_tier_impact?: number;
}

export interface AnomaliesState {
  anomalies: Anomaly[];
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
  total_count: number;
  has_more: boolean;
  active_recovery_count: number;
}

export interface Recovery {
  recovery_id: UUID;
  persona_id: UUID;
  sovereign_id: UUID;
  agent_name: string;
  entry_reason: string;
  tier_at_entry: number;
  tier_current: number;
  weeks_elapsed: number;
  entry_at: string;
  expected_exit_at?: string;
  recovery_status: string;
  anomaly_count_in_recovery: number;
  last_tier_increase_at?: string;
  is_approved: boolean; // Fail-closed: false by default
}

export interface RecoveryState {
  recoveries: Recovery[];
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
  total_count: number;
  has_more: boolean;
}

/**
 * Hook: Fetch recent agent actions
 * Polls every 5 seconds for real-time updates
 */
export function useAgentActions(sovereignId: UUID): AgentActionsState {
  const [state, setState] = useState<AgentActionsState>({
    actions: [],
    loading: false,
    error: null,
    last_updated_at: null,
    total_count: 0,
    has_more: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const fetchActions = async () => {
      try {
        const resp = await fetch(
          `/api/graph/projections/agent-actions?sovereign_id=${sovereignId}&limit=50`,
          { signal: controller.signal }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (isMounted) {
          setState({
            actions: data.actions || [],
            loading: false,
            error: null,
            last_updated_at: data.generated_at || new Date().toISOString(),
            total_count: data.total_count || 0,
            has_more: data.has_more || false,
          });
        }
      } catch (err) {
        if (isMounted && !(err instanceof Error && err.name === 'AbortError')) {
          setState((prev) => ({
            ...prev,
            error: String(err),
            loading: false,
          }));
        }
      }
    };

    fetchActions();
    const interval = setInterval(fetchActions, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
      controller.abort();
    };
  }, [sovereignId]);

  return state;
}

/**
 * Hook: Fetch anomalies with optional filtering
 * Polls every 5 seconds
 */
export function useAnomalies(
  sovereignId: UUID,
  severity?: string,
  anomalyType?: string
): AnomaliesState {
  const [state, setState] = useState<AnomaliesState>({
    anomalies: [],
    loading: false,
    error: null,
    last_updated_at: null,
    total_count: 0,
    has_more: false,
    active_recovery_count: 0,
  });

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const fetchAnomalies = async () => {
      try {
        const params = new URLSearchParams({
          sovereign_id: String(sovereignId),
          limit: '50',
        });
        if (severity) params.append('severity', severity);
        if (anomalyType) params.append('anomaly_type', anomalyType);

        const resp = await fetch(`/api/graph/projections/anomalies?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (isMounted) {
          setState({
            anomalies: data.anomalies || [],
            loading: false,
            error: null,
            last_updated_at: data.generated_at || new Date().toISOString(),
            total_count: data.total_count || 0,
            has_more: data.has_more || false,
            active_recovery_count: data.active_recovery_count || 0,
          });
        }
      } catch (err) {
        if (isMounted && !(err instanceof Error && err.name === 'AbortError')) {
          setState((prev) => ({
            ...prev,
            error: String(err),
            loading: false,
          }));
        }
      }
    };

    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
      controller.abort();
    };
  }, [sovereignId, severity, anomalyType]);

  return state;
}

/**
 * Hook: Fetch recovery status
 * Polls every 5 seconds
 */
export function useRecovery(sovereignId: UUID): RecoveryState {
  const [state, setState] = useState<RecoveryState>({
    recoveries: [],
    loading: false,
    error: null,
    last_updated_at: null,
    total_count: 0,
    has_more: false,
  });

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const fetchRecovery = async () => {
      try {
        const resp = await fetch(
          `/api/graph/projections/recovery?sovereign_id=${sovereignId}&limit=25`,
          { signal: controller.signal }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (isMounted) {
          setState({
            recoveries: data.recoveries || [],
            loading: false,
            error: null,
            last_updated_at: data.generated_at || new Date().toISOString(),
            total_count: data.total_count || 0,
            has_more: data.has_more || false,
          });
        }
      } catch (err) {
        if (isMounted && !(err instanceof Error && err.name === 'AbortError')) {
          setState((prev) => ({
            ...prev,
            error: String(err),
            loading: false,
          }));
        }
      }
    };

    fetchRecovery();
    const interval = setInterval(fetchRecovery, 5000);

    return () => {
      isMounted = false;
      clearInterval(interval);
      controller.abort();
    };
  }, [sovereignId]);

  return state;
}

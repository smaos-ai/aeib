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
  lastUpdated: Date;
  totalCount: number;
  hasMore: boolean;
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
  lastUpdated: Date;
  totalCount: number;
  hasMore: boolean;
  activeRecoveryCount: number;
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
}

export interface RecoveryState {
  recoveries: Recovery[];
  loading: boolean;
  error: string | null;
  lastUpdated: Date;
  totalCount: number;
  hasMore: boolean;
}

/**
 * Hook: Fetch recent agent actions
 * Polls every 5 seconds for real-time updates
 */
export function useAgentActions(sovereignId: UUID): AgentActionsState {
  const [state, setState] = useState<AgentActionsState>({
    actions: [],
    loading: true,
    error: null,
    lastUpdated: new Date(),
    totalCount: 0,
    hasMore: false,
  });

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const resp = await fetch(
          `/api/graph/projections/agent_actions?sovereign_id=${sovereignId}&limit=50`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        setState({
          actions: data.actions || [],
          loading: false,
          error: null,
          lastUpdated: new Date(),
          totalCount: data.total_count || 0,
          hasMore: data.has_more || false,
        });
      } catch (err) {
        setState((prev) => ({
          ...prev,
          error: String(err),
          loading: false,
        }));
      }
    };

    // Fetch immediately
    fetchActions();

    // Poll every 5 seconds
    const interval = setInterval(fetchActions, 5000);
    return () => clearInterval(interval);
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
    loading: true,
    error: null,
    lastUpdated: new Date(),
    totalCount: 0,
    hasMore: false,
    activeRecoveryCount: 0,
  });

  useEffect(() => {
    const fetchAnomalies = async () => {
      try {
        const params = new URLSearchParams({
          sovereign_id: String(sovereignId),
          limit: '50',
        });
        if (severity) params.append('severity', severity);
        if (anomalyType) params.append('anomaly_type', anomalyType);

        const resp = await fetch(`/api/graph/projections/anomalies?${params.toString()}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        setState({
          anomalies: data.anomalies || [],
          loading: false,
          error: null,
          lastUpdated: new Date(),
          totalCount: data.total_count || 0,
          hasMore: data.has_more || false,
          activeRecoveryCount: data.active_recovery_count || 0,
        });
      } catch (err) {
        setState((prev) => ({
          ...prev,
          error: String(err),
          loading: false,
        }));
      }
    };

    fetchAnomalies();
    const interval = setInterval(fetchAnomalies, 5000);
    return () => clearInterval(interval);
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
    loading: true,
    error: null,
    lastUpdated: new Date(),
    totalCount: 0,
    hasMore: false,
  });

  useEffect(() => {
    const fetchRecovery = async () => {
      try {
        const resp = await fetch(
          `/api/graph/projections/recovery?sovereign_id=${sovereignId}&limit=25`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        setState({
          recoveries: data.recoveries || [],
          loading: false,
          error: null,
          lastUpdated: new Date(),
          totalCount: data.total_count || 0,
          hasMore: data.has_more || false,
        });
      } catch (err) {
        setState((prev) => ({
          ...prev,
          error: String(err),
          loading: false,
        }));
      }
    };

    fetchRecovery();
    const interval = setInterval(fetchRecovery, 5000);
    return () => clearInterval(interval);
  }, [sovereignId]);

  return state;
}

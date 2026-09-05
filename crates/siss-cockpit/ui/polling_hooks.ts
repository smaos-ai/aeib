/// Phase 24: React Polling Hooks Implementation
/// useAgentActions, useAnomalies, useRecovery hooks for real-time execution tracking
///
/// Each hook:
/// - Polls its respective endpoint immediately on mount
/// - Continues polling every 5000ms (configurable)
/// - Handles errors gracefully
/// - Cleans up interval on unmount
/// - Respects dependency changes

import React from 'react';

// =====================================================================
// TYPE DEFINITIONS
// =====================================================================

export interface AgentAction {
  action_id: string;
  agent_id?: string;
  action?: string;
  timestamp?: string;
  [key: string]: any;
}

export interface AgentActionsResponse {
  actions: AgentAction[];
  total_count: number;
  has_more: boolean;
  generated_at: string;
}

export interface AgentActionsState {
  actions: AgentAction[];
  total_count: number;
  has_more: boolean;
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
}

export interface Anomaly {
  sovereign_id?: string;
  anomaly_type?: string;
  severity?: number;
  detected_at?: string;
  [key: string]: any;
}

export interface AnomaliesResponse {
  anomalies: Anomaly[];
  active_recovery_count: number;
  total_count: number;
  has_more: boolean;
  generated_at: string;
}

export interface AnomaliesState {
  anomalies: Anomaly[];
  active_recovery_count: number;
  total_count: number;
  has_more: boolean;
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
}

export interface RecoveryEvent {
  recovery_id: string;
  sovereign_id: string;
  entry_reason: string;
  entry_at: string;
  weeks_elapsed: number;
  exit_status: string | null;
  exit_at: string | null;
  expected_exit_at: string;
  tier_at_entry: number;
  current_tier: number;
}

export interface RecoveryResponse {
  recoveries: RecoveryEvent[];
  total_count: number;
  has_more: boolean;
  generated_at: string;
}

export interface RecoveryState {
  recoveries: RecoveryEvent[];
  total_count: number;
  has_more: boolean;
  loading: boolean;
  error: string | null;
  last_updated_at: string | null;
}

// =====================================================================
// POLLING HOOKS
// =====================================================================

/**
 * useAgentActions - Polls /api/graph/projections/agent-actions for a given sovereign
 *
 * @param sovereignId - UUID of the sovereign entity to track
 * @param intervalMs - Polling interval in milliseconds (default: 5000)
 * @returns AgentActionsState with actions array, metadata, loading, and error states
 */
export function useAgentActions(sovereignId: string, intervalMs: number = 5000): AgentActionsState {
  const [state, setState] = React.useState<AgentActionsState>({
    actions: [],
    total_count: 0,
    has_more: false,
    loading: false,
    error: null,
    last_updated_at: null,
  });

  React.useEffect(() => {
    // Immediate first poll on mount
    const poll = async () => {
      try {
        const url = `/api/graph/projections/agent-actions?sovereign_id=${encodeURIComponent(sovereignId)}`;

        const res = await fetch(url);
        if (res.ok) {
          const data: AgentActionsResponse = await res.json();
          setState({
            actions: data.actions,
            total_count: data.total_count,
            has_more: data.has_more,
            loading: false,
            error: null,
            last_updated_at: new Date().toISOString(),
          });
        } else {
          setState(prev => ({
            ...prev,
            loading: false,
            error: `HTTP ${res.status}`,
          }));
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        setState(prev => ({
          ...prev,
          loading: false,
          error: errorMsg,
        }));
      }
    };

    // Call immediately
    poll();

    // Set up interval
    const interval = setInterval(poll, intervalMs);

    // Cleanup
    return () => clearInterval(interval);
  }, [sovereignId, intervalMs]);

  return state;
}

/**
 * useAnomalies - Polls /api/graph/projections/anomalies for a given sovereign
 *
 * @param sovereignId - UUID of the sovereign entity to track
 * @param severity - Optional filter by severity level (e.g., "high", "critical")
 * @param anomalyType - Optional filter by anomaly type (e.g., "dispute_spam")
 * @param intervalMs - Polling interval in milliseconds (default: 5000)
 * @returns AnomaliesState with anomalies array, metadata, loading, and error states
 */
export function useAnomalies(
  sovereignId: string,
  severity?: string,
  anomalyType?: string,
  intervalMs: number = 5000
): AnomaliesState {
  const [state, setState] = React.useState<AnomaliesState>({
    anomalies: [],
    active_recovery_count: 0,
    total_count: 0,
    has_more: false,
    loading: false,
    error: null,
    last_updated_at: null,
  });

  React.useEffect(() => {
    // Immediate first poll on mount
    const poll = async () => {
      try {
        const params = new URLSearchParams();
        params.append('sovereign_id', sovereignId);
        if (severity) {
          params.append('severity', severity);
        }
        if (anomalyType) {
          params.append('anomaly_type', anomalyType);
        }
        const url = `/api/graph/projections/anomalies?${params.toString()}`;

        const res = await fetch(url);
        if (res.ok) {
          const data: AnomaliesResponse = await res.json();
          setState({
            anomalies: data.anomalies,
            active_recovery_count: data.active_recovery_count,
            total_count: data.total_count,
            has_more: data.has_more,
            loading: false,
            error: null,
            last_updated_at: new Date().toISOString(),
          });
        } else {
          setState(prev => ({
            ...prev,
            loading: false,
            error: `HTTP ${res.status}`,
          }));
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        setState(prev => ({
          ...prev,
          loading: false,
          error: errorMsg,
        }));
      }
    };

    // Call immediately
    poll();

    // Set up interval
    const interval = setInterval(poll, intervalMs);

    // Cleanup
    return () => clearInterval(interval);
  }, [sovereignId, severity, anomalyType, intervalMs]);

  return state;
}

/**
 * useRecovery - Polls /api/graph/projections/recovery for a given sovereign
 *
 * @param sovereignId - UUID of the sovereign entity to track
 * @param intervalMs - Polling interval in milliseconds (default: 5000)
 * @returns RecoveryState with recoveries array, metadata, loading, and error states
 */
export function useRecovery(sovereignId: string, intervalMs: number = 5000): RecoveryState {
  const [state, setState] = React.useState<RecoveryState>({
    recoveries: [],
    total_count: 0,
    has_more: false,
    loading: false,
    error: null,
    last_updated_at: null,
  });

  React.useEffect(() => {
    // Immediate first poll on mount
    const poll = async () => {
      try {
        const url = `/api/graph/projections/recovery?sovereign_id=${encodeURIComponent(sovereignId)}`;

        const res = await fetch(url);
        if (res.ok) {
          const data: RecoveryResponse = await res.json();
          setState({
            recoveries: data.recoveries,
            total_count: data.total_count,
            has_more: data.has_more,
            loading: false,
            error: null,
            last_updated_at: new Date().toISOString(),
          });
        } else {
          setState(prev => ({
            ...prev,
            loading: false,
            error: `HTTP ${res.status}`,
          }));
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        setState(prev => ({
          ...prev,
          loading: false,
          error: errorMsg,
        }));
      }
    };

    // Call immediately
    poll();

    // Set up interval
    const interval = setInterval(poll, intervalMs);

    // Cleanup
    return () => clearInterval(interval);
  }, [sovereignId, intervalMs]);

  return state;
}

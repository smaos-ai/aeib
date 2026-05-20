import React from 'react';
import { UUID } from 'crypto';
import { useRecovery } from '../hooks/useProjections';

interface RecoveryStatusProps {
  sovereignId: UUID;
}

/**
 * Recovery lifecycle dashboard
 * Shows agents in recovery mode: entry reason, tier progress, anomaly count
 * Updates every 5 seconds
 */
export function RecoveryStatus({ sovereignId }: RecoveryStatusProps) {
  const { recoveries, loading, error, lastUpdated, totalCount } = useRecovery(sovereignId);

  if (error) {
    return (
      <div className="recovery recovery--error">
        <h2>Recovery Status</h2>
        <p className="error-text">❌ {error}</p>
      </div>
    );
  }

  const statusIcon = {
    active: '🔴',
    completed: '🟡',
    exited: '🟢',
  };

  const statusLabel = {
    active: 'Active',
    completed: 'Completed',
    exited: 'Exited',
  };

  return (
    <div className="recovery">
      <h2>Recovery Status ({recoveries.length})</h2>

      <div className="recovery-meta">
        <span className="total-count">Total: {totalCount}</span>
        <span className="last-updated">Updated: {lastUpdated.toLocaleTimeString()}</span>
      </div>

      {loading && recoveries.length === 0 && (
        <div className="loading-spinner">
          <p>Loading recovery data...</p>
        </div>
      )}

      <div className="recoveries-list">
        {recoveries.map((recovery) => {
          const progressPct = Math.min((recovery.weeks_elapsed / 4) * 100, 100);
          const tierDelta = recovery.tier_current - recovery.tier_at_entry;

          if (!recovery.is_approved) {
            return (
              <div
                key={recovery.recovery_id}
                className="recovery-card recovery-card--locked"
              >
                <div className="recovery-card-header">
                  <div className="agent-info">
                    <span className="agent-name">{recovery.agent_name}</span>
                    <span className="status-badge status-active">🔒 LOCKED</span>
                  </div>
                </div>
                <div className="recovery-locked-message">
                  Recovery entry pending approval. Reason: {recovery.entry_reason}
                </div>
              </div>
            );
          }

          return (
            <div key={recovery.recovery_id} className="recovery-card">
              <div className="recovery-card-header">
                <div className="agent-info">
                  <span className="agent-name">{recovery.agent_name}</span>
                  <span className={`status-badge status-${recovery.recovery_status}`}>
                    {statusIcon[recovery.recovery_status as keyof typeof statusIcon] || '?'}
                    {statusLabel[recovery.recovery_status as keyof typeof statusLabel]}
                  </span>
                </div>
                <span className="reason">{recovery.entry_reason}</span>
              </div>

              <div className="recovery-card-body">
                <div className="recovery-metric">
                  <span className="label">Tier Progress</span>
                  <div className="tier-row">
                    <span className="tier-before">{recovery.tier_at_entry}</span>
                    <span className="tier-arrow">→</span>
                    <span className={`tier-after ${tierDelta >= 0 ? 'positive' : 'negative'}`}>
                      {recovery.tier_current} {tierDelta > 0 ? `(+${tierDelta})` : ''}
                    </span>
                  </div>
                </div>

                <div className="recovery-metric">
                  <span className="label">Timeline</span>
                  <div className="timeline">
                    <span className="weeks">{recovery.weeks_elapsed}w elapsed</span>
                    {recovery.expected_exit_at && (
                      <span className="expected-exit">
                        Est. exit: {new Date(recovery.expected_exit_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>

                <div className="recovery-metric">
                  <span className="label">Anomalies in Recovery</span>
                  <span className="anomaly-count">{recovery.anomaly_count_in_recovery}</span>
                </div>
              </div>

              <div className="recovery-card-progress">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${progressPct}%` }}></div>
                </div>
                <span className="progress-label">{progressPct.toFixed(0)}% to 4-week exit</span>
              </div>

              <div className="recovery-card-footer">
                <time>
                  Entered: {new Date(recovery.entry_at).toLocaleDateString()}
                  {recovery.last_tier_increase_at && (
                    <> • Last increase: {new Date(recovery.last_tier_increase_at).toLocaleDateString()}</>
                  )}
                </time>
              </div>
            </div>
          );
        })}
      </div>

      {recoveries.length === 0 && !loading && (
        <p className="empty-state">✓ No agents in recovery</p>
      )}
    </div>
  );
}

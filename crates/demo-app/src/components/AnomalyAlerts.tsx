import React from 'react';
import { UUID } from 'crypto';
import { useAnomalies } from '../hooks/useProjections';

interface AnomalyAlertsProps {
  sovereignId: UUID;
}

/**
 * Real-time anomaly alert dashboard
 * Shows severity levels: low (blue), medium (yellow), high (orange), critical (red)
 * Updates every 5 seconds
 */
export function AnomalyAlerts({ sovereignId }: AnomalyAlertsProps) {
  const {
    anomalies,
    loading,
    error,
    lastUpdated,
    activeRecoveryCount,
  } = useAnomalies(sovereignId);

  if (error) {
    return (
      <div className="alerts alerts--error">
        <h2>Anomalies</h2>
        <p className="error-text">❌ {error}</p>
      </div>
    );
  }

  const severityColor = {
    low: 'alert--low',
    medium: 'alert--medium',
    high: 'alert--high',
    critical: 'alert--critical',
  };

  const severityIcon = {
    low: 'ⓘ',
    medium: '⚠',
    high: '⚠️',
    critical: '🚨',
  };

  return (
    <div className="alerts">
      <div className="alerts-header">
        <h2>Anomalies ({anomalies.length})</h2>
        <div className="alerts-badges">
          {activeRecoveryCount > 0 && (
            <span className="badge badge--recovery">
              🔴 {activeRecoveryCount} agents in recovery
            </span>
          )}
        </div>
      </div>

      <div className="alerts-meta">
        <span className="last-updated">Updated: {lastUpdated.toLocaleTimeString()}</span>
      </div>

      {loading && anomalies.length === 0 && (
        <div className="loading-spinner">
          <p>Loading anomalies...</p>
        </div>
      )}

      <div className="alerts-list">
        {anomalies.map((anomaly) => (
          <div
            key={anomaly.anomaly_id}
            className={`alert ${severityColor[anomaly.severity as keyof typeof severityColor] || 'alert--unknown'}`}
          >
            <div className="alert-icon">{severityIcon[anomaly.severity as keyof typeof severityIcon] || '?'}</div>

            <div className="alert-content">
              <div className="alert-type">{anomaly.anomaly_type}</div>
              <div className="alert-details">
                <span className="detail">
                  <span className="label">Count:</span>
                  <span className="value">{anomaly.event_count} events</span>
                </span>
                <span className="detail">
                  <span className="label">Window:</span>
                  <span className="value">{anomaly.window_hours}h</span>
                </span>
                <span className="detail">
                  <span className="label">Severity:</span>
                  <span className={`value severity ${anomaly.severity}`}>{anomaly.severity.toUpperCase()}</span>
                </span>
              </div>
              {anomaly.recovery_triggered && (
                <div className="alert-recovery-badge">
                  Recovery triggered • Tier impact: {anomaly.recovery_tier_impact}
                </div>
              )}
            </div>

            <div className="alert-time">
              <time>{new Date(anomaly.detected_at).toLocaleTimeString()}</time>
            </div>
          </div>
        ))}
      </div>

      {anomalies.length === 0 && !loading && (
        <p className="empty-state">✓ No anomalies in the last 7 days</p>
      )}
    </div>
  );
}

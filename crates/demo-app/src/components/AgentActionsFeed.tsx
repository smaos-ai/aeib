import React from 'react';
import { UUID } from 'crypto';
import { useAgentActions } from '../hooks/useProjections';

interface AgentActionsFeedProps {
  sovereignId: UUID;
}

/**
 * Real-time feed of agent actions
 * Updates every 5 seconds via polling
 */
export function AgentActionsFeed({ sovereignId }: AgentActionsFeedProps) {
  const { actions, loading, error, lastUpdated, totalCount } = useAgentActions(sovereignId);

  if (error) {
    return (
      <div className="feed feed--error">
        <h2>Agent Actions</h2>
        <p className="error-text">❌ {error}</p>
      </div>
    );
  }

  return (
    <div className="feed">
      <h2>Agent Actions ({actions.length})</h2>
      <div className="feed-meta">
        <span className="total-count">Total: {totalCount}</span>
        <span className="last-updated">
          Updated: {lastUpdated.toLocaleTimeString()}
        </span>
      </div>

      {loading && actions.length === 0 && (
        <div className="loading-spinner">
          <p>Loading actions...</p>
        </div>
      )}

      <div className="actions-list">
        {actions.map((action) => (
          <div key={action.action_id} className="action-card">
            <div className="action-card-header">
              <span className="event-type">{action.event_type}</span>
              <span className="tier-change">
                {action.tier_before} → {action.tier_after}
              </span>
            </div>

            <div className="action-card-body">
              <div className="action-detail">
                <span className="label">Cost:</span>
                <span className="value cost">{action.cost_incurred} tokens</span>
              </div>
              <div className="action-detail">
                <span className="label">Lineage:</span>
                <span className={`value lineage ${action.lineage_safe ? 'safe' : 'unsafe'}`}>
                  {action.lineage_safe ? '✓ Safe' : '⚠ Unsafe'}
                </span>
              </div>
              <div className="action-detail">
                <span className="label">Session:</span>
                <span className="value session-id">{action.session_id.toString().slice(0, 8)}...</span>
              </div>
            </div>

            <div className="action-card-footer">
              <time>{new Date(action.scored_at).toLocaleTimeString()}</time>
            </div>
          </div>
        ))}
      </div>

      {actions.length === 0 && !loading && (
        <p className="empty-state">No actions in the last hour</p>
      )}
    </div>
  );
}

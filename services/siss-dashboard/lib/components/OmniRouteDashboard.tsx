/// Phase 38: OmniRoute Control Tower Dashboard
/// Master component integrating SSE streaming, A2UI rendering, RCE state preservation, and AP2 mandates

import React, { useState } from 'react';
import { A2UIRenderer, ProjectionResolverResponse } from './A2UIRenderer';
import { SSEStreamListener, SSEStreamEvent } from './SSEStreamListener';
import { DecisionWebhookForm, DecisionWebhookPayload } from './DecisionWebhookForm';

interface DashboardState {
  isStreaming: boolean;
  currentProjection: ProjectionResolverResponse | null;
  rceContext: Record<string, unknown> | null;
  waitingForDecision: boolean;
  lastEvent: SSEStreamEvent | null;
}

/// OmniRoute Control Tower with fail-closed invariants
export const OmniRouteDashboard: React.FC = () => {
  const [dashboardState, setDashboardState] = useState<DashboardState>({
    isStreaming: true,
    currentProjection: null,
    rceContext: null,
    waitingForDecision: false,
    lastEvent: null
  });

  const handleSSEEvent = (event: SSEStreamEvent) => {
    setDashboardState(prevState => ({
      ...prevState,
      lastEvent: event,
      isStreaming: event.event_type !== 'DECISION_REQUIRED'
    }));

    // Fail-closed: Handle DECISION_REQUIRED event
    if (event.event_type === 'DECISION_REQUIRED') {
      setDashboardState(prevState => ({
        ...prevState,
        waitingForDecision: true,
        isStreaming: false,
        rceContext: event.payload.context || event.payload
      }));
    }

    // Fail-closed: Handle QUARANTINED status
    if (event.payload?.status === 'QUARANTINED') {
      setDashboardState(prevState => ({
        ...prevState,
        waitingForDecision: true,
        isStreaming: false,
        rceContext: event.payload.execution_context || event.payload
      }));
    }
  };

  const handleDecisionSubmit = (payload: DecisionWebhookPayload) => {
    // Fail-closed: Validate decision payload structure
    if (!payload.workflow_id || !payload.decision || !payload.timestamp || !payload.human_operator_id) {
      console.error('Invalid decision payload structure');
      return;
    }

    // Resume streaming after decision
    setDashboardState(prevState => ({
      ...prevState,
      waitingForDecision: false,
      isStreaming: true
    }));

    console.log('Decision submitted:', payload);
  };

  // Mock projection for rendering
  const mockProjection: ProjectionResolverResponse = {
    workflow_id: 'wf-omniroute-001',
    layout: {
      type: 'card',
      title: 'Agent Canvas',
      fields: [
        { type: 'text_field', label: 'Agent ID' },
        { type: 'badge', label: 'Status' },
        { type: 'text_field', label: 'Session' },
        { type: 'text_field', label: 'Uptime' }
      ]
    },
    data_binding: {
      agent_id: '$.agent.id',
      status: '$.agent.status',
      session: '$.agent.session',
      uptime: '$.metrics.uptime'
    },
    metadata: {
      component_count: 4,
      decoupled: true,
      version: '1.0'
    }
  };

  return (
    <div data-testid="omniroute-dashboard" className="omniroute-control-tower">
      <header className="dashboard-header">
        <h1>OmniRoute Control Tower</h1>
        <div className="status-bar">
          <span className={`streaming-status ${dashboardState.isStreaming ? 'active' : 'halted'}`}>
            {dashboardState.isStreaming ? '🟢 Streaming' : '⏹ Halted'}
          </span>
          {dashboardState.waitingForDecision && (
            <span className="decision-status">⏳ Awaiting Human Decision</span>
          )}
        </div>
      </header>

      <main className="dashboard-content">
        {/* SSE Stream Listener */}
        <section className="sse-section">
          <h2>Real-Time Swarm Sync</h2>
          <SSEStreamListener onEvent={handleSSEEvent} />
        </section>

        {/* A2UI Renderer */}
        {!dashboardState.waitingForDecision && (
          <section className="a2ui-section">
            <h2>Universal Agent Canvas</h2>
            <A2UIRenderer projection={mockProjection} />
          </section>
        )}

        {/* RCE Context Display (Halted) */}
        {dashboardState.waitingForDecision && dashboardState.rceContext && (
          <section className="rce-context-section">
            <h2>🚨 RCE Execution Context (Read-Only)</h2>
            <div className="rce-dump">
              <pre>{JSON.stringify(dashboardState.rceContext, null, 2)}</pre>
            </div>
          </section>
        )}

        {/* Decision Form (Human-in-the-Loop) */}
        {dashboardState.waitingForDecision && dashboardState.lastEvent && (
          <section className="decision-section">
            <h2>Strategic Operator Decision Required</h2>
            <DecisionWebhookForm
              workflowId={dashboardState.lastEvent.workflow_id}
              onSubmit={handleDecisionSubmit}
            />
          </section>
        )}
      </main>

      <footer className="dashboard-footer">
        <p>Phase 38: OmniRoute Control Tower & A2UI Dashboard Integration</p>
        {dashboardState.lastEvent && (
          <p>Last Event: {dashboardState.lastEvent.event_type} @ {dashboardState.lastEvent.timestamp}</p>
        )}
      </footer>
    </div>
  );
};

export default OmniRouteDashboard;

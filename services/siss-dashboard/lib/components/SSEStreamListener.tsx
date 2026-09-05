/// Phase 38: SSE Stream Listener Component
/// Real-time binding to /api/rce/stream with RCE state preservation

import React, { useEffect, useState } from 'react';

export interface SSEStreamEvent {
  event_type: 'ROUTING' | 'METRICS' | 'STATUS' | 'DECISION_REQUIRED';
  workflow_id: string;
  timestamp: string;
  payload: Record<string, unknown>;
  agent_id: string;
}

interface SSEStreamListenerProps {
  onEvent: (event: SSEStreamEvent) => void;
}

/// SSE Stream Listener with fail-closed invariants
export const SSEStreamListener: React.FC<SSEStreamListenerProps> = ({ onEvent }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [eventCount, setEventCount] = useState(0);

  useEffect(() => {
    // Establish EventSource connection to /api/rce/stream
    let eventSource: EventSource | null = null;

    const connectSSE = () => {
      try {
        eventSource = new EventSource('/api/rce/stream');

        eventSource.onopen = () => {
          setIsConnected(true);
          setIsStreaming(true);
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const sseEvent: SSEStreamEvent = data;

            // Fail-closed: Validate event structure
            if (!sseEvent.event_type || !sseEvent.workflow_id || !sseEvent.timestamp) {
              console.error('Invalid SSE event structure');
              return;
            }

            // Fail-closed: Halt streaming on DECISION_REQUIRED or QUARANTINED
            if (sseEvent.event_type === 'DECISION_REQUIRED' || sseEvent.payload?.status === 'QUARANTINED') {
              setIsStreaming(false);
              // Do not emit further events; await human decision
              return;
            }

            // RFC3339 timestamp validation
            const rfc3339Regex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
            if (!rfc3339Regex.test(sseEvent.timestamp)) {
              console.error('Invalid RFC3339 timestamp format');
              return;
            }

            // Emit event to parent component
            onEvent(sseEvent);
            setEventCount(prev => prev + 1);
          } catch (error) {
            console.error('Failed to parse SSE event:', error);
          }
        };

        eventSource.onerror = () => {
          setIsConnected(false);
          setIsStreaming(false);
          eventSource?.close();
        };
      } catch (error) {
        console.error('Failed to establish SSE connection:', error);
      }
    };

    connectSSE();

    return () => {
      if (eventSource) {
        eventSource.close();
        setIsConnected(false);
        setIsStreaming(false);
      }
    };
  }, [onEvent]);

  return (
    <div data-testid="sse-stream-listener" className="sse-listener">
      <div className="connection-status">
        <span className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
        <span className={`streaming-badge ${isStreaming ? 'streaming' : 'halted'}`}>
          {isStreaming ? 'Streaming' : 'Halted'}
        </span>
        <span className="event-count">Events: {eventCount}</span>
      </div>
    </div>
  );
};

export default SSEStreamListener;

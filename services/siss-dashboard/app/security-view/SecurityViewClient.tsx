/// Phase 34: Security View Client Component
/// Handles real-time SSE streaming of AoE events mapped to A2UI components

'use client';

import React, { useEffect, useState, useRef } from 'react';

interface ValidatedComponentEvent {
  timestamp: string;
  jsx: string;
  schema_valid: boolean;
  accessibility: {
    passed: boolean;
    violations: string[];
  };
  component: {
    type: string;
    id: string;
    [key: string]: any;
  };
}

interface SecurityViewState {
  events: ValidatedComponentEvent[];
  sessionId: string | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

export default function SecurityViewClient() {
  const [state, setState] = useState<SecurityViewState>({
    events: [],
    sessionId: null,
    isConnected: false,
    isLoading: true,
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const connectionAttempts = useRef(0);
  const maxRetries = 3;

  /// Initialize security session and connect to stream
  useEffect(() => {
    const initSession = async () => {
      try {
        // Generate session ID
        const sessionId = generateSessionId();
        setState(prev => ({
          ...prev,
          sessionId,
          isLoading: true,
        }));

        // Connect to SSE stream
        connectToStream(sessionId);
      } catch (error) {
        setState(prev => ({
          ...prev,
          error: error instanceof Error ? error.message : 'Failed to initialize session',
          isLoading: false,
        }));
      }
    };

    initSession();

    // Cleanup on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  /// Connect to security stream SSE endpoint
  const connectToStream = (sessionId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const streamUrl = `/api/security/stream?session_id=${sessionId}`;

    try {
      const eventSource = new EventSource(streamUrl);

      eventSource.addEventListener('open', () => {
        setState(prev => ({
          ...prev,
          isConnected: true,
          isLoading: false,
          error: null,
        }));
        connectionAttempts.current = 0;
      });

      eventSource.addEventListener('message', (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as ValidatedComponentEvent;
          setState(prev => ({
            ...prev,
            events: [data, ...prev.events].slice(0, 100), // Keep last 100 events
          }));
        } catch (error) {
          console.error('Failed to parse event:', error);
        }
      });

      eventSource.addEventListener('error', () => {
        eventSource.close();
        setState(prev => ({
          ...prev,
          isConnected: false,
        }));

        // Retry with exponential backoff
        if (connectionAttempts.current < maxRetries) {
          connectionAttempts.current += 1;
          const delay = Math.min(1000 * Math.pow(2, connectionAttempts.current), 10000);
          setTimeout(() => connectToStream(sessionId), delay);
        } else {
          setState(prev => ({
            ...prev,
            error: 'Connection failed after multiple attempts',
          }));
        }
      });

      eventSourceRef.current = eventSource;
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to connect to stream',
        isLoading: false,
      }));
    }
  };

  /// Render component based on A2UI type
  const renderComponent = (event: ValidatedComponentEvent) => {
    const { component, timestamp, accessibility } = event;

    // Use the pre-rendered JSX if available
    if (event.jsx) {
      return (
        <div
          key={timestamp}
          className="border border-gray-700 rounded-lg p-4 bg-gray-900 mb-4"
          dangerouslySetInnerHTML={{ __html: event.jsx }}
        />
      );
    }

    // Fallback: render based on component type
    switch (component.type) {
      case 'alert':
        return (
          <div
            key={timestamp}
            className={`border-l-4 p-4 mb-4 rounded ${
              component.level === 'error'
                ? 'border-red-500 bg-red-900 bg-opacity-20'
                : 'border-yellow-500 bg-yellow-900 bg-opacity-20'
            }`}
          >
            <div className="font-semibold text-white">
              {component.message || 'Alert'}
            </div>
            {!accessibility.passed && (
              <div className="text-sm text-gray-400 mt-1">
                Accessibility: {accessibility.violations.join(', ')}
              </div>
            )}
          </div>
        );

      case 'badge':
        return (
          <div
            key={timestamp}
            className={`inline-block px-3 py-1 rounded-full text-sm font-medium mr-2 mb-2 ${
              component.color === 'green'
                ? 'bg-green-900 text-green-100'
                : 'bg-blue-900 text-blue-100'
            }`}
          >
            {component.label}
          </div>
        );

      case 'text':
        return (
          <div key={timestamp} className="text-gray-300 mb-2 font-mono text-sm">
            {component.content}
          </div>
        );

      case 'progress':
        return (
          <div key={timestamp} className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-gray-400">
                {component.label || 'Progress'}
              </span>
              <span className="text-sm font-semibold text-blue-400">
                {component.value}/{component.max}
              </span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{
                  width: `${(component.value / component.max) * 100}%`,
                }}
              />
            </div>
          </div>
        );

      case 'table':
        return (
          <div key={timestamp} className="mb-4 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-700">
                  {component.headers?.map((header: string, i: number) => (
                    <th
                      key={i}
                      className="text-left py-2 px-4 text-gray-300 font-semibold"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {component.rows?.map((row: string[], i: number) => (
                  <tr key={i} className="border-b border-gray-800 hover:bg-gray-800">
                    {row.map((cell: string, j: number) => (
                      <td key={j} className="py-2 px-4 text-gray-400">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      default:
        return (
          <div
            key={timestamp}
            className="bg-gray-800 border border-gray-700 rounded p-4 mb-4"
          >
            <div className="text-xs text-gray-500 mb-2">{component.type}</div>
            <div className="text-gray-300">
              {JSON.stringify(component, null, 2)}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="flex items-center justify-between bg-gray-900 border border-gray-700 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full ${
              state.isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-gray-300">
            {state.isLoading
              ? 'Connecting...'
              : state.isConnected
              ? 'Connected (Real-time)'
              : 'Disconnected'}
          </span>
          {state.sessionId && (
            <span className="text-xs text-gray-500 ml-auto font-mono">
              Session: {state.sessionId.substring(0, 8)}...
            </span>
          )}
        </div>
      </div>

      {/* Error Display */}
      {state.error && (
        <div className="bg-red-900 bg-opacity-20 border border-red-500 rounded-lg p-4">
          <div className="font-semibold text-red-300">Error</div>
          <div className="text-red-200 text-sm mt-1">{state.error}</div>
        </div>
      )}

      {/* Events Display */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
        {state.events.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-500 mb-2">
              {state.isLoading ? 'Waiting for events...' : 'No events received yet'}
            </div>
            {state.isConnected && (
              <div className="text-xs text-gray-600">
                Events will appear here as they occur
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {state.events.map((event) => renderComponent(event))}
          </div>
        )}
      </div>

      {/* Event Count */}
      {state.events.length > 0 && (
        <div className="text-right text-sm text-gray-500">
          Showing {state.events.length} of {state.events.length + 500}+ events
        </div>
      )}
    </div>
  );
}

/// Generate a unique session ID (UUID v4)
function generateSessionId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

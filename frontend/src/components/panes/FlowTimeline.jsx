import React, { useEffect, useState, useRef } from 'react'
import { Card, H4, Tag, Button } from '@blueprintjs/core'

const STATUS_CONFIG = {
  pending: { color: '#999999', bg: '#99999915', icon: '⏳' },
  active: { color: '#0066cc', bg: '#0066cc15', icon: '▶️' },
  complete: { color: '#00aa00', bg: '#00aa0015', icon: '✅' },
  blocked: { color: '#ff8800', bg: '#ff880015', icon: '🚫' },
  failed: { color: '#ff0000', bg: '#ff000015', icon: '❌' },
  halted: { color: '#ff0000', bg: '#ff000015', icon: '🛑' },
  waiting_human: { color: '#ff8800', bg: '#ff880015', icon: '👤' },
}

const SPAN_TYPE_ICONS = {
  system_orchestration: '🔷',
  policy_classification: '🏷️',
  verification: '✔️',
  identity_attestation: '🔐',
  delegation_check: '📋',
  sandbox_simulation: '📦',
  veto_gate_intervention: '🛑',
  cryptographic_signing: '🔑',
  ledger_commit: '💾',
}

export default function FlowTimeline() {
  const [traces, setTraces] = useState([])
  const [selectedTrace, setSelectedTrace] = useState(null)
  const [expandedSpans, setExpandedSpans] = useState(new Set())
  const [liveSpans, setLiveSpans] = useState([])
  const eventSourceRef = useRef(null)
  const timelineRef = useRef(null)

  // Fetch recent traces
  useEffect(() => {
    const fetchTraces = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/traces/?limit=20')
        const data = await res.json()
        setTraces(data || [])
      } catch (err) {
        console.error('Failed to fetch traces:', err)
      }
    }
    fetchTraces()
    const interval = setInterval(fetchTraces, 5000)
    return () => clearInterval(interval)
  }, [])

  // Load full trace
  const loadTrace = async (traceId) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/traces/${traceId}`)
      const data = await res.json()
      setSelectedTrace(data)
      setLiveSpans([])
      startLiveStream(traceId)
    } catch (err) {
      console.error('Failed to load trace:', err)
    }
  }

  // SSE live streaming
  const startLiveStream = (traceId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`http://127.0.0.1:8000/api/traces/${traceId}/stream`)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.span && !data.heartbeat) {
          setLiveSpans(prev => [...prev, data.span])
        }
      } catch (err) {
        console.error('Parse error:', err)
      }
    }
    es.onerror = () => es.close()
    eventSourceRef.current = es
  }

  // Toggle span expansion
  const toggleSpan = (spanId) => {
    setExpandedSpans(prev => {
      const next = new Set(prev)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  // Auto-scroll
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight
    }
  }, [liveSpans])

  const spans = selectedTrace?.spans
    ? Object.values(selectedTrace.spans).sort((a, b) => a.sequence - b.sequence)
    : liveSpans

  const getTimelineScale = (spans) => {
    if (!spans.length) return { start: 0, total: 1 }
    const start = Math.min(...spans.map(s => s.start_time))
    const end = Math.max(...spans.map(s => s.end_time || s.start_time))
    return { start, total: Math.max(end - start, 0.001) }
  }

  const scale = getTimelineScale(spans)

  const renderSpan = (span, index, parentId = null) => {
    const config = STATUS_CONFIG[span.status] || STATUS_CONFIG.pending
    const isExpanded = expandedSpans.has(span.span_id)
    const leftPct = ((span.start_time - scale.start) / scale.total) * 100
    const widthPct = span.duration_ms
      ? Math.max((span.duration_ms / (scale.total * 1000)) * 100, 2)
      : 2

    return (
      <div key={span.span_id}>
        {/* Span Row */}
        <div
          onClick={() => toggleSpan(span.span_id)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px',
            borderRadius: '4px',
            cursor: 'pointer',
            background: isExpanded ? '#f0f0f0' : 'transparent',
            transition: 'all 0.2s ease',
            marginLeft: parentId ? '24px' : '0px',
          }}
        >
          {/* Step number */}
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '14px',
              border: `2px solid ${config.color}`,
              background: config.bg,
              minWidth: '28px',
            }}
          >
            {SPAN_TYPE_ICONS[span.span_type] || '📋'}
          </div>

          {/* Span info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '12px', fontWeight: '600', color: '#333' }}>
              {span.name}
            </div>
            <div style={{ fontSize: '10px', color: '#666', marginTop: '2px' }}>
              {span.duration_ms != null ? `${span.duration_ms.toFixed(1)}ms` : 'running...'}
              {' · '}
              <span style={{ fontFamily: 'monospace', fontSize: '9px' }}>
                {new Date(span.start_time * 1000).toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Status badge */}
          <Tag
            minimal
            intent={span.status === 'complete' ? 'success' : span.status === 'failed' ? 'danger' : 'none'}
            style={{ fontSize: '10px' }}
          >
            {config.icon} {span.status.toUpperCase()}
          </Tag>

          {/* Timing bar */}
          <div
            style={{
              width: '120px',
              height: '6px',
              background: '#e0e0e0',
              borderRadius: '3px',
              overflow: 'hidden',
              marginLeft: '8px',
            }}
          >
            <div
              style={{
                height: '100%',
                background: config.color,
                marginLeft: `${leftPct}%`,
                width: `${widthPct}%`,
                transition: 'all 0.3s ease',
              }}
            />
          </div>

          {/* Expand indicator */}
          <span style={{ fontSize: '12px', color: '#999', marginLeft: '8px' }}>
            {isExpanded ? '▼' : '▶'}
          </span>
        </div>

        {/* Expanded payload */}
        {isExpanded && (
          <div
            style={{
              marginLeft: '44px',
              marginTop: '4px',
              marginBottom: '8px',
              padding: '10px',
              background: '#f9f9f9',
              borderRadius: '4px',
              border: '1px solid #e0e0e0',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {/* Payload */}
              <div>
                <h4 style={{ fontSize: '10px', fontWeight: '600', color: '#666', margin: '0 0 6px 0' }}>
                  PAYLOAD
                </h4>
                <pre
                  style={{
                    fontSize: '8px',
                    background: '#ffffff',
                    padding: '6px',
                    borderRadius: '3px',
                    overflow: 'auto',
                    maxHeight: '120px',
                    margin: 0,
                    border: '1px solid #ddd',
                    color: '#333',
                  }}
                >
                  {JSON.stringify(span.payload, null, 2)}
                </pre>
              </div>

              {/* Metadata */}
              <div>
                <h4 style={{ fontSize: '10px', fontWeight: '600', color: '#666', margin: '0 0 6px 0' }}>
                  METADATA
                </h4>
                <div style={{ fontSize: '9px', color: '#666', lineHeight: '1.6' }}>
                  <p style={{ margin: '2px 0' }}>
                    <span style={{ color: '#999' }}>Span:</span>{' '}
                    <span style={{ fontFamily: 'monospace' }}>{span.span_id}</span>
                  </p>
                  <p style={{ margin: '2px 0' }}>
                    <span style={{ color: '#999' }}>Type:</span> {span.span_type}
                  </p>
                  <p style={{ margin: '2px 0' }}>
                    <span style={{ color: '#999' }}>Merkle:</span>{' '}
                    <span style={{ fontFamily: 'monospace', color: '#0066cc' }}>
                      {(span.merkle_root || 'N/A').slice(0, 16)}...
                    </span>
                  </p>
                  {span.error && (
                    <p style={{ margin: '2px 0', color: '#ff0000' }}>
                      <span style={{ color: '#999' }}>Error:</span> {span.error}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Child spans */}
        {span.child_span_ids?.length > 0 &&
          span.child_span_ids
            .map(childId =>
              Object.values(selectedTrace?.spans || {}).find(s => s.span_id === childId)
            )
            .filter(Boolean)
            .map((child, i) => renderSpan(child, i, span.span_id))}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: '12px' }}>
      {/* Left: Trace List */}
      <div
        style={{
          width: '280px',
          borderRight: '1px solid #e0e0e0',
          overflowY: 'auto',
          padding: '12px',
        }}
      >
        <H4 style={{ margin: '0 0 12px 0', fontSize: '13px' }}>
          📊 Execution Traces ({traces.length})
        </H4>
        {traces.map((t) => (
          <button
            key={t.trace_id}
            onClick={() => loadTrace(t.trace_id)}
            style={{
              width: '100%',
              textAlign: 'left',
              padding: '8px',
              marginBottom: '6px',
              border: selectedTrace?.trace_id === t.trace_id ? '2px solid #0066cc' : '1px solid #ddd',
              borderRadius: '4px',
              background: selectedTrace?.trace_id === t.trace_id ? '#f0f8ff' : '#ffffff',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ fontSize: '10px', fontWeight: '600', color: '#333' }}>
              {t.trace_id}
            </div>
            <div style={{ fontSize: '9px', color: '#999', marginTop: '2px' }}>
              {t.span_count} spans · {t.total_duration_ms ?? '...'}ms
            </div>
            <div style={{ fontSize: '8px', color: '#0066cc', fontFamily: 'monospace', marginTop: '2px' }}>
              {t.merkle_root}
            </div>
          </button>
        ))}
      </div>

      {/* Right: Timeline View */}
      <div ref={timelineRef} style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        {!selectedTrace && liveSpans.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#999', marginTop: '40px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
            <div style={{ fontSize: '13px' }}>Select a trace to see the timeline</div>
          </div>
        ) : (
          <>
            {/* Trace header */}
            {selectedTrace && (
              <Card style={{ padding: '12px', marginBottom: '12px', background: '#f9f9f9' }}>
                <div style={{ fontSize: '12px', fontWeight: '600', color: '#333' }}>
                  {selectedTrace.trace_id}
                </div>
                <div style={{ fontSize: '10px', color: '#666', marginTop: '4px' }}>
                  {selectedTrace.span_count} spans · {selectedTrace.total_duration_ms}ms
                </div>
                <div style={{ fontSize: '9px', fontFamily: 'monospace', color: '#0066cc', marginTop: '4px' }}>
                  Merkle: {selectedTrace.merkle_root?.slice(0, 32)}...
                </div>
              </Card>
            )}

            {/* Spans */}
            {spans.map((span, i) => !span.parent_span_id && renderSpan(span, i))}

            {/* Complete footer */}
            {selectedTrace?.status === 'complete' && (
              <Card
                style={{
                  padding: '10px',
                  marginTop: '12px',
                  background: '#f0fff0',
                  border: '1px solid #00aa00',
                }}
              >
                <div style={{ fontSize: '11px', color: '#00aa00', fontWeight: '600' }}>
                  ✅ Flow complete — {selectedTrace.total_duration_ms}ms · {selectedTrace.span_count} steps
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}

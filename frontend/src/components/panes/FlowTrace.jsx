import React, { useState, useEffect } from 'react'
import { Card, H4, Tag } from '@blueprintjs/core'
import { useGovernance } from '../../state/GovernanceContext'

export default function FlowTrace() {
  const { state } = useGovernance()
  const [events, setEvents] = useState([])

  // Build event log from state changes
  useEffect(() => {
    const log = []
    const now = new Date()

    if (state.intents.length > 0) {
      const intent = state.intents[state.intents.length - 1]
      log.push({
        order: 1,
        time: new Date(intent.submittedAt || now),
        event: '📥 Intent Submitted',
        details: `Capsule: ${state.capsuleId}`,
        data: JSON.stringify(intent.fields, null, 2),
        status: 'complete',
      })
    }

    if (state.classifications.length > 0) {
      const classification = state.classifications[state.classifications.length - 1]
      log.push({
        order: 2,
        time: new Date(classification.computedAt || now),
        event: '🔍 Classification Computed',
        details: `Severity: ${classification.highestSeverity.toUpperCase()} | Rules: ${classification.matchedRules.length}`,
        data: JSON.stringify({
          badge: classification.badgeLabel,
          rules: classification.matchedRules.map(r => r.classification),
        }, null, 2),
        status: 'complete',
      })

      if (classification.highestSeverity === 'block') {
        log.push({
          order: 3,
          time: new Date(classification.computedAt || now),
          event: '🛑 Layer 7 Veto Gate Triggered',
          details: 'HIGH-RISK: Requires human authorization',
          data: JSON.stringify({
            halt_reason: 'Classification blocked',
            rules_violated: classification.matchedRules.map(r => ({
              id: r.id,
              severity: r.severity,
              citation: r.citation.split('\n')[0],
            })),
          }, null, 2),
          status: state.resolvedIntentId === state.currentIntentId ? 'complete' : 'pending',
        })
      }
    }

    if (state.resolvedIntentId === state.currentIntentId && state.receipts.length > 0) {
      const receipt = state.receipts[state.receipts.length - 1]
      log.push({
        order: 4,
        time: new Date(receipt.timestamp),
        event: '✅ Authorization Signed (Ed25519)',
        details: `Algorithm: ${receipt.alg} | Verified: ${receipt.verified ? '✓' : '✗'}`,
        data: JSON.stringify({
          action: receipt.payload?.action,
          signature: receipt.signatureBase64?.slice(0, 40) + '...',
          publicKey: receipt.publicKeyBase64?.slice(0, 40) + '...',
        }, null, 2),
        status: 'complete',
      })

      log.push({
        order: 5,
        time: new Date(),
        event: '💾 Receipt Persisted to Ledger',
        details: `Receipt ID: ${receipt.id.slice(0, 12)}...`,
        data: JSON.stringify({
          ledger: '/tmp/agentacct.db',
          table: 'agentacct_ledger',
          merkle_root: 'sha256(...)',
          git_commit: '5430f8d2',
        }, null, 2),
        status: 'complete',
      })
    }

    setEvents(log)
  }, [state.intents, state.classifications, state.resolvedIntentId, state.receipts])

  if (events.length === 0) {
    return (
      <Card style={{ padding: '12px', background: '#f9f9f9', borderRadius: '4px' }}>
        <div style={{ fontSize: '12px', color: '#999999', textAlign: 'center' }}>
          Flow trace appears here as you interact with the system.
        </div>
      </Card>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <H4 style={{ margin: '0 0 12px 0', fontSize: '14px' }}>🔄 Execution Flow Trace</H4>

      {events.map((evt, idx) => (
        <Card
          key={idx}
          style={{
            padding: '10px',
            background: evt.status === 'complete' ? '#f0fff0' : '#ffffee',
            borderLeft: `3px solid ${evt.status === 'complete' ? '#00aa00' : '#ffb81c'}`,
            borderRadius: '4px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <div style={{ fontSize: '16px', minWidth: '24px' }}>{evt.event.split(' ')[0]}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#333' }}>
                {evt.event.split(' ').slice(1).join(' ')}
              </div>
              <div style={{ fontSize: '10px', color: '#666', marginTop: '2px' }}>
                {evt.details}
              </div>
              <div style={{ fontSize: '10px', color: '#999', marginTop: '3px' }}>
                {evt.time.toISOString().split('T')[1].slice(0, 8)}
              </div>
              {evt.data && (
                <details style={{ marginTop: '6px' }}>
                  <summary style={{ fontSize: '9px', color: '#0066cc', cursor: 'pointer' }}>
                    View payload
                  </summary>
                  <pre
                    style={{
                      fontSize: '8px',
                      background: '#ffffff',
                      padding: '6px',
                      borderRadius: '3px',
                      overflow: 'auto',
                      maxHeight: '150px',
                      margin: '4px 0 0 0',
                      border: '1px solid #e0e0e0',
                      color: '#333',
                    }}
                  >
                    {evt.data}
                  </pre>
                </details>
              )}
            </div>
            <Tag minimal intent={evt.status === 'complete' ? 'success' : 'warning'}>
              {evt.status === 'complete' ? '✓' : '⏳'}
            </Tag>
          </div>
        </Card>
      ))}
    </div>
  )
}

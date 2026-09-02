import React, { useEffect, useState } from 'react'
import { Card, H4, ProgressBar, Tag, Button } from '@blueprintjs/core'
import { buildDiamondGraph } from '../../lib/graphBuilder'
import { getCapsule } from '../../lib/capsules'
import { useGovernance } from '../../state/GovernanceContext'
import { signPayload } from '../../lib/signing'

const statusStyles = {
  pending: { color: '#999999', icon: '⏳', bg: '#f9f9f9', border: '1px solid #d0d0d0' },
  running: { color: '#0066cc', icon: '▶️', bg: '#e8f4ff', border: '2px solid #0066cc', animation: 'pulse 1s infinite' },
  success: { color: '#00aa00', icon: '✓', bg: '#f0fff0', border: '2px solid #00aa00' },
  failed: { color: '#dd0000', icon: '✗', bg: '#fff0f0', border: '2px solid #dd0000' },
  blocked: { color: '#ff8800', icon: '🚫', bg: '#fff8f0', border: '2px solid #ff8800' },
  halted: { color: '#666666', icon: '⏸', bg: '#f5f5f5', border: '1px solid #999999' },
  gate: { color: '#ff8800', icon: '🔐', bg: '#fff8f0', border: '2px solid #ff8800', animation: 'pulse 0.8s infinite' },
}

export default function CenterWorkPane() {
  const { state, addReceipt, resolveIntent } = useGovernance()
  const [nodeList, setNodeList] = useState([])
  const [executionPhase, setExecutionPhase] = useState('idle') // idle, preparing, executing, decision, complete
  const [startTime, setStartTime] = useState(null)

  useEffect(() => {
    const currentIntent = state.intents[state.intents.length - 1]
    const currentClassification = state.classifications[state.classifications.length - 1]

    if (currentIntent && currentClassification) {
      const capsule = getCapsule(state.capsuleId)
      const { nodes } = buildDiamondGraph(capsule, currentIntent, currentClassification)
      setNodeList(nodes)
      setExecutionPhase('preparing')
      setStartTime(Date.now())

      // Simulate execution phases
      setTimeout(() => setExecutionPhase('executing'), 300)
    }
  }, [state.intents, state.classifications, state.capsuleId])

  const successCount = nodeList.filter(n => n.status === 'success').length
  const failedCount = nodeList.filter(n => n.status === 'failed').length
  const blockedCount = nodeList.filter(n => n.status === 'blocked' || n.kind === 'gate').length
  const progress = nodeList.length > 0 ? ((successCount + failedCount + blockedCount) / nodeList.length) * 100 : 0

  // Check if any node is blocked (veto gate)
  const blockedNode = nodeList.find(n => n.status === 'blocked' || n.kind === 'gate')
  const classification = state.classifications[state.classifications.length - 1]

  if (nodeList.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '16px', color: '#999999', padding: '40px' }}>
        <div style={{ fontSize: '48px' }}>📊</div>
        <div style={{ textAlign: 'center', lineHeight: '1.6' }}>
          <div style={{ fontSize: '14px', fontWeight: '600', color: '#333' }}>No Active Execution</div>
          <div style={{ fontSize: '12px', marginTop: '4px' }}>Submit an intent to see the diamond topology execution graph.</div>
        </div>
      </div>
    )
  }

  // Handle veto gate
  const handleVetoAuthorize = async () => {
    try {
      console.log('Authorize button clicked')
      const receipt = await signPayload({
        action: 'veto.authorize',
        classification: classification?.badgeLabel,
        rules: classification?.matchedRules?.map(r => r.classification) || [],
        timestamp: new Date().toISOString(),
      })
      console.log('Receipt generated:', receipt)
      addReceipt(receipt)
      resolveIntent(state.currentIntentId)
      console.log('Receipt added successfully, intent resolved')
    } catch (error) {
      console.error('Authorize failed:', error)
      alert(`ERROR: ${error.message}`)
    }
  }

  const handleVetoRevise = async () => {
    try {
      const receipt = await signPayload({
        action: 'veto.revise',
        classification: classification?.badgeLabel,
        decision: 'REJECTED_BY_CRO',
        timestamp: new Date().toISOString(),
      })
      addReceipt(receipt)
    } catch (error) {
      console.error('Revise failed:', error)
    }
  }

  return (
    <div style={{ padding: '16px', overflowY: 'auto', height: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* VETO GATE CARD (If Blocked and Not Resolved) */}
      {blockedNode && classification?.highestSeverity === 'block' && state.resolvedIntentId !== state.currentIntentId && (
        <Card style={{
          background: '#fff0f0',
          border: '3px solid #dd0000',
          padding: '16px',
          borderRadius: '8px',
          boxShadow: '0 4px 20px rgba(221, 0, 0, 0.2)',
          animation: 'pulse 1s infinite'
        }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <div style={{ fontSize: '32px', minWidth: '40px' }}>🔐</div>
            <div style={{ flex: 1 }}>
              <H4 style={{ margin: '0 0 8px 0', color: '#dd0000', fontSize: '16px' }}>
                ⚠️ EXECUTION BLOCKED
              </H4>
              <div style={{ fontSize: '13px', fontWeight: '600', color: '#dd0000', marginBottom: '8px' }}>
                {classification?.badgeLabel}
              </div>
              <div style={{ fontSize: '11px', color: '#333', lineHeight: '1.6', marginBottom: '12px' }}>
                <strong>Why blocked:</strong> {classification?.matchedRules?.[0]?.classification}
                <div style={{ marginTop: '6px', paddingLeft: '8px', borderLeft: '2px solid #dd0000', fontSize: '10px', color: '#666' }}>
                  Legal basis: {classification?.matchedRules?.[0]?.citation?.split('\n')[0]}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button
                  text="✓ Authorize & Sign (Ed25519)"
                  intent="danger"
                  large
                  onClick={handleVetoAuthorize}
                  style={{ flex: 1, fontWeight: 'bold' }}
                />
                <Button
                  text="🚫 Veto & Abort"
                  intent="warning"
                  large
                  onClick={handleVetoRevise}
                  style={{ flex: 1, fontWeight: 'bold' }}
                />
              </div>
              <div style={{ fontSize: '9px', color: '#dd0000', marginTop: '8px', fontWeight: 'bold' }}>
                👆 Click one of these buttons to proceed
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Header */}
      <div>
        <H4 style={{ margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🔷 Execution Pipeline</span>
          <Tag minimal>{executionPhase === 'executing' ? 'RUNNING' : executionPhase === 'decision' ? 'DECISION GATE' : 'PREPARING'}</Tag>
        </H4>
        <ProgressBar value={progress / 100} intent={blockedCount > 0 ? 'warning' : successCount > 0 ? 'success' : 'primary'} />
        <div style={{ fontSize: '11px', color: '#666', marginTop: '6px' }}>
          ✓ {successCount} completed · ✗ {failedCount} failed · 🚫 {blockedCount} blocked · ⏳ {nodeList.filter(n => ['pending', 'running'].includes(n.status)).length} in progress
        </div>
      </div>

      {/* Execution timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {nodeList.map((node, idx) => {
          const style = statusStyles[node.status] || statusStyles.pending
          const isGate = node.kind === 'gate'
          const isCurrentFocus = (node.status === 'running' || node.status === 'blocked') && idx > 0

          return (
            <div key={node.id} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
              {/* Connector line */}
              {idx > 0 && (
                <div style={{
                  width: '2px',
                  height: '24px',
                  background: isCurrentFocus ? '#0066cc' : '#d0d0d0',
                  marginTop: '-8px'
                }} />
              )}

              {/* Node card */}
              <Card
                style={{
                  flex: 1,
                  padding: '10px',
                  background: style.bg,
                  border: style.border,
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  animation: style.animation ? style.animation : 'none',
                  boxShadow: isCurrentFocus ? '0 0 12px rgba(0, 102, 204, 0.4)' : 'none',
                  transform: isCurrentFocus ? 'scale(1.02)' : 'scale(1)'
                }}
              >
                <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  {/* Icon + Status */}
                  <div style={{ fontSize: '18px', minWidth: '24px' }}>
                    {style.icon}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: '600', fontSize: '12px', color: style.color }}>
                      {node.label}
                    </div>
                    <div style={{ fontSize: '10px', color: '#666', marginTop: '3px' }}>
                      {node.kind === 'intent' && '📥 User Intent'}
                      {node.kind === 'tool' && `🔧 Tool Call: ${node.toolName}`}
                      {node.kind === 'gate' && '🔐 Pre-Execution Gate (EU AI Act Article 14)'}
                      {node.kind === 'converge' && '⚙️ Merge Point'}
                      {node.kind === 'retry' && '🔁 Retry Branch'}
                    </div>
                    {node.riskFlag && (
                      <div style={{ fontSize: '10px', color: '#dd0000', fontWeight: 'bold', marginTop: '4px' }}>
                        ⚠️ HIGH-RISK: Requires CRO authorization
                      </div>
                    )}
                  </div>

                  {/* Status badge */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                    <Tag minimal intent={node.status === 'success' ? 'success' : node.status === 'failed' ? 'danger' : 'none'}>
                      {node.status.toUpperCase()}
                    </Tag>
                    {node.status === 'running' && (
                      <div style={{ fontSize: '9px', color: '#0066cc', fontWeight: 'bold', animation: 'blink 1s infinite' }}>
                        EXECUTING...
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            </div>
          )
        })}
      </div>

      {/* Execution summary */}
      {blockedCount > 0 && (
        <Card style={{ background: '#fff8f0', border: '1px solid #ff8800', padding: '12px', borderRadius: '4px' }}>
          <div style={{ fontSize: '12px', color: '#ff8800', fontWeight: 'bold', marginBottom: '4px' }}>
            🔐 Execution Suspended
          </div>
          <div style={{ fontSize: '11px', color: '#333', lineHeight: '1.5' }}>
            One or more nodes are blocked by pre-execution veto gates. Human authorization required before proceeding. Check the right panel to review and authorize.
          </div>
        </Card>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        @keyframes blink {
          0%, 50%, 100% { opacity: 1; }
          25%, 75% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

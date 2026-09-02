import React, { useState } from 'react'
import { Handle, Position } from '@xyflow/react'
import { Button } from '@blueprintjs/core'
import { signPayload } from '../../../lib/signing'
import { useGovernance } from '../../../state/GovernanceContext'

export default function InlineVetoGateNode({ data, selected }) {
  const { addReceipt } = useGovernance()
  const [resolving, setResolving] = useState(false)

  const classification = data.classification || {}
  const matchedRules = classification.matchedRules || []

  const handleAuthorize = async () => {
    setResolving(true)
    const receipt = await signPayload({
      action: 'veto.authorize',
      nodeId: data.nodeId,
      classification: classification.badgeLabel,
      resolvedAt: new Date().toISOString(),
    })
    addReceipt(receipt)
    setResolving(false)
    // Note: CenterWorkPane's stepper would then advance to next node
  }

  const handleRevise = async () => {
    setResolving(true)
    const receipt = await signPayload({
      action: 'veto.revise',
      nodeId: data.nodeId,
      classification: classification.badgeLabel,
      resolvedAt: new Date().toISOString(),
    })
    addReceipt(receipt)
    setResolving(false)
    // Note: Would trigger re-submission of intent
  }

  return (
    <div
      style={{
        background: '#fff0f0',
        border: '2px solid #dd0000',
        borderRadius: '8px',
        padding: '12px',
        minWidth: '200px',
        maxWidth: '300px',
        boxShadow: selected ? '0 0 12px #dd0000' : 'none',
      }}
    >
      <Handle type="target" position={Position.Top} />

      {/* A2UI Card title */}
      <div style={{ fontSize: '12px', fontWeight: '700', color: '#dd0000', marginBottom: '8px', textTransform: 'uppercase' }}>
        🚫 Human Authorization Required
      </div>

      {/* Classification badge */}
      <div style={{ fontSize: '13px', fontWeight: '600', color: '#dd0000', marginBottom: '8px' }}>
        {classification.badgeLabel}
      </div>

      {/* Matched rules (the reason) */}
      <div style={{ fontSize: '11px', color: '#333333', marginBottom: '8px', lineHeight: '1.4', background: '#fafafa', padding: '6px', borderRadius: '4px' }}>
        {matchedRules.map((rule, i) => (
          <div key={i} style={{ marginBottom: i < matchedRules.length - 1 ? '4px' : '0' }}>
            <strong>{rule.classification}</strong>
          </div>
        ))}
      </div>

      {/* Citation excerpt */}
      {matchedRules.length > 0 && (
        <div style={{ fontSize: '10px', color: '#666666', marginBottom: '8px', lineHeight: '1.3', maxHeight: '100px', overflowY: 'auto', background: '#fefefe', padding: '6px', borderLeft: '2px solid #dd0000', borderRadius: '3px' }}>
          <strong>Legal Basis:</strong> {matchedRules[0]?.citation?.split('\n')[1] || matchedRules[0]?.citation?.slice(0, 60)}...
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '6px' }}>
        <Button
          text="Authorize"
          intent="danger"
          size="small"
          onClick={handleAuthorize}
          disabled={resolving}
          style={{ flex: 1 }}
        />
        <Button
          text="Revise"
          intent="warning"
          size="small"
          onClick={handleRevise}
          disabled={resolving}
          style={{ flex: 1 }}
        />
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

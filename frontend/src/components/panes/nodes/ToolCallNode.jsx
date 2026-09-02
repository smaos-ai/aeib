import React from 'react'
import { Handle, Position } from '@xyflow/react'

export default function ToolCallNode({ data, selected }) {
  const statusColors = {
    pending: '#cccccc',
    running: '#0066cc',
    success: '#00aa00',
    failed: '#dd0000',
    blocked: '#dd0000',
    retrying: '#ff8800',
    halted: '#999999',
  }

  const statusEmoji = {
    pending: '⏳',
    running: '▶️',
    success: '✓',
    failed: '✗',
    blocked: '🚫',
    retrying: '🔄',
    halted: '⏸',
  }

  const statusLabel = {
    pending: 'Pending',
    running: 'Running',
    success: 'Success',
    failed: 'Failed',
    blocked: 'Blocked',
    retrying: 'Retrying',
    halted: 'Halted',
  }

  const color = statusColors[data.status] || '#cccccc'

  return (
    <div
      style={{
        background: '#ffffff',
        border: `2px solid ${color}`,
        borderRadius: '8px',
        padding: '12px',
        minWidth: '140px',
        boxShadow: selected ? `0 0 8px ${color}` : 'none',
        opacity: data.status === 'halted' ? 0.6 : 1,
      }}
    >
      <Handle type="target" position={Position.Top} />

      {/* Node icon/emoji based on kind */}
      <div style={{ textAlign: 'center', marginBottom: '4px', fontSize: '18px' }}>
        {data.kind === 'tool' ? '⚙️' : data.kind === 'retry' ? '🔄' : data.kind === 'converge' ? '🔀' : '•'}
      </div>

      {/* Node label */}
      <div style={{ fontSize: '12px', fontWeight: '600', color: '#000000', lineHeight: '1.3', marginBottom: '6px', textAlign: 'center' }}>
        {data.label}
      </div>

      {/* Status pill */}
      <div
        style={{
          fontSize: '10px',
          fontWeight: 'bold',
          color: '#ffffff',
          background: color,
          padding: '4px 8px',
          borderRadius: '4px',
          textAlign: 'center',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
        }}
      >
        {statusEmoji[data.status]} {statusLabel[data.status]}
      </div>

      {/* Risk flag indicator */}
      {data.riskFlag && (
        <div style={{ fontSize: '9px', color: '#dd0000', fontWeight: 'bold', marginTop: '6px', textAlign: 'center', background: '#fff0f0', padding: '2px', borderRadius: '3px' }}>
          HIGH-RISK FLAG
        </div>
      )}

      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

import React from 'react'
import { Card, H5 } from '@blueprintjs/core'
import { computeSessionStats } from '../../lib/sessionStats'
import { useGovernance } from '../../state/GovernanceContext'

export default function DriftIndicator() {
  const { state } = useGovernance()
  const stats = computeSessionStats(state)

  const statusColor = stats.driftFlag ? '#dd0000' : '#00aa00'
  const statusLabel = stats.driftFlag ? '⚠️ DRIFT DETECTED' : '✓ NORMAL'

  return (
    <Card
      style={{
        background: `${statusColor}22`,
        border: `1px solid ${statusColor}`,
        padding: '12px',
      }}
    >
      <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
        📊 Behavioral Drift
      </H5>

      <div style={{ fontSize: '12px', fontWeight: '700', color: statusColor, marginBottom: '4px' }}>
        {statusLabel}
      </div>

      <div style={{ fontSize: '10px', color: '#666666' }}>
        Veto trigger rate: <strong>{stats.driftRate}%</strong> (baseline: 20%)
      </div>
    </Card>
  )
}

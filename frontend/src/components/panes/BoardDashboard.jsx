import React from 'react'
import { Card, H5 } from '@blueprintjs/core'
import { computeSessionStats } from '../../lib/sessionStats'
import { useGovernance } from '../../state/GovernanceContext'

export default function BoardDashboard() {
  const { state } = useGovernance()
  const stats = computeSessionStats(state)

  const tiles = [
    { label: 'Exposure', value: stats.exposure, color: '#0066cc', emoji: '📊' },
    { label: 'Risk', value: stats.risk, color: stats.riskSeverity === 'block' ? '#dd0000' : '#ff8800', emoji: '⚠️' },
    { label: 'Controls', value: stats.controls, color: '#00aa00', emoji: '✓' },
    { label: 'Exceptions', value: stats.exceptions, color: '#ff8800', emoji: '🚫' },
    { label: 'Incidents', value: stats.incidents, color: stats.incidentsCount > 0 ? '#dd0000' : '#cccccc', emoji: '🔥' },
    { label: 'Regulatory', value: stats.regulatoryExposureLabel, color: '#6600cc', emoji: '⚖️' },
    { label: 'Decisions', value: stats.decisions, color: '#00aa00', emoji: '✔️' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
        📈 Board Dashboard
      </H5>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        {tiles.map((tile, i) => (
          <Card
            key={i}
            style={{
              background: `${tile.color}11`,
              border: `1px solid ${tile.color}`,
              padding: '10px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '20px', marginBottom: '4px' }}>{tile.emoji}</div>
            <div style={{ fontSize: '10px', color: '#999999', marginBottom: '4px', textTransform: 'uppercase', fontWeight: '600' }}>
              {tile.label}
            </div>
            <div style={{ fontSize: '12px', fontWeight: '700', color: tile.color }}>
              {tile.value}
            </div>
          </Card>
        ))}
      </div>

      {/* Drift warning */}
      {stats.driftFlag && (
        <Card style={{ background: '#fff0f0', border: '1px solid #dd0000', padding: '8px' }}>
          <div style={{ fontSize: '11px', color: '#dd0000', fontWeight: 'bold' }}>
            ⚠️ DRIFT DETECTED: {stats.driftRate}% of actions trigger veto gates (baseline: 20%)
          </div>
        </Card>
      )}
    </div>
  )
}

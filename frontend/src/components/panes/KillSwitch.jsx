import React from 'react'
import { Button, H5, Card } from '@blueprintjs/core'
import { useGovernance } from '../../state/GovernanceContext'

export default function KillSwitch() {
  const { state, engageKillSwitch } = useGovernance()

  const haltedNodeCount = state.graphState?.nodes?.filter(n => n.status === 'halted').length || 0

  return (
    <Card
      style={{
        background: state.killSwitchEngaged ? '#fff0f0' : '#f9fafb',
        border: `1px solid ${state.killSwitchEngaged ? '#dd0000' : '#cccccc'}`,
        padding: '12px',
      }}
    >
      <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
        ⏸ Kill Switch
      </H5>

      <Button
        text={state.killSwitchEngaged ? `✓ ENGAGED (${haltedNodeCount} nodes halted)` : 'Engage Kill Switch'}
        intent={state.killSwitchEngaged ? 'danger' : 'primary'}
        onClick={engageKillSwitch}
        disabled={state.killSwitchEngaged}
        fill
      />

      {state.killSwitchEngaged && (
        <div style={{ fontSize: '11px', color: '#dd0000', marginTop: '8px', fontWeight: 'bold' }}>
          All execution halted. Refresh to reset.
        </div>
      )}
    </Card>
  )
}

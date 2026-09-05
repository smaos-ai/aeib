import React, { useEffect } from 'react'
import { Card, H5 } from '@blueprintjs/core'
import { useGovernance } from '../../state/GovernanceContext'

export default function PoolStatusWidget() {
  const { state, setPoolStatus } = useGovernance()

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8080/api/pool/status', { timeout: 2000 })
        if (res.ok) {
          const data = await res.json()
          setPoolStatus(data)
        }
      } catch (e) {
        // Silent fail — backend not running
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [setPoolStatus])

  const poolSize = state.poolStatus?.pool_size ?? '—'
  const poolMax = state.poolStatus?.pool_max ?? '—'
  const hasPoolData = state.poolStatus !== null

  return (
    <Card
      style={{
        background: hasPoolData ? '#f0fef9' : '#f9fafb',
        border: `1px solid ${hasPoolData ? '#00aa00' : '#cccccc'}`,
        padding: '12px',
      }}
    >
      <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
        ◆ Pool Status
      </H5>

      <div style={{ fontSize: '12px', fontWeight: '700', color: hasPoolData ? '#00aa00' : '#999999', marginBottom: '8px' }}>
        {poolSize}/{poolMax} sandboxes ready
      </div>

      {!hasPoolData && (
        <div style={{ fontSize: '10px', color: '#999999' }}>
          Backend not running at localhost:8080
        </div>
      )}

      {hasPoolData && state.poolStatus?.sandboxes && (
        <div style={{ fontSize: '10px', color: '#666666', marginTop: '8px' }}>
          {state.poolStatus.sandboxes.map((sb, i) => (
            <div key={i}>
              Container {i + 1}: {sb.container_id?.slice(0, 12) || '—'}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

import React, { useState } from 'react'
import { Button, Card, H5 } from '@blueprintjs/core'
import { useNetworkIsolation } from '../../lib/useNetworkIsolation'
import NetworkIsolationTerminal from '../NetworkIsolationTerminal'

export default function NetworkStatusWidget() {
  const netStatus = useNetworkIsolation(7000)
  const [showModal, setShowModal] = useState(false)

  const statusColor = netStatus.isolated ? '#00aa00' : netStatus.browserOnline ? '#ff8800' : '#cccccc'
  const statusLabel = netStatus.verdict || 'TESTING...'

  return (
    <>
      <Card
        style={{
          background: `${statusColor}22`,
          border: `1px solid ${statusColor}`,
          padding: '12px',
        }}
      >
        <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
          🌐 Network Status
        </H5>

        <div style={{ fontSize: '12px', fontWeight: '700', color: statusColor, marginBottom: '8px' }}>
          {statusLabel}
        </div>

        <Button
          text="View Full Diagnostics"
          size="small"
          intent={netStatus.isolated ? 'success' : 'warning'}
          onClick={() => setShowModal(true)}
          fill
        />
      </Card>

      {showModal && <NetworkIsolationTerminal onClose={() => setShowModal(false)} />}
    </>
  )
}

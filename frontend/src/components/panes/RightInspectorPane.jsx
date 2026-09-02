import React from 'react'
import ReceiptLedger from './ReceiptLedger'
import BoardDashboard from './BoardDashboard'
import KillSwitch from './KillSwitch'
import NetworkStatusWidget from './NetworkStatusWidget'
import PoolStatusWidget from './PoolStatusWidget'
import DriftIndicator from './DriftIndicator'

export default function RightInspectorPane() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', background: '#ffffff', height: '100%', overflowY: 'auto' }}>
      {/* Receipt Ledger (proof layer) */}
      <ReceiptLedger />

      <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #cccccc' }} />

      {/* Board Dashboard */}
      <BoardDashboard />

      <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #cccccc' }} />

      {/* Control & monitoring widgets */}
      <KillSwitch />
      <NetworkStatusWidget />
      <PoolStatusWidget />
      <DriftIndicator />
    </div>
  )
}

import React from 'react'
import ReceiptLedger from './ReceiptLedger'
import FlowTrace from './FlowTrace'

export default function RightInspectorPane() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', background: '#ffffff', height: '100%', overflowY: 'auto' }}>
      {/* Flow Trace (execution timeline) */}
      <FlowTrace />

      <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #cccccc' }} />

      {/* Receipt Ledger (proof layer) */}
      <ReceiptLedger />
    </div>
  )
}

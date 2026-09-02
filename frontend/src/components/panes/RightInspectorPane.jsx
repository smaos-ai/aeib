import React, { useState } from 'react'
import { Button } from '@blueprintjs/core'
import ReceiptLedger from './ReceiptLedger'
import FlowTimeline from './FlowTimeline'

export default function RightInspectorPane() {
  const [activeTab, setActiveTab] = useState('timeline') // 'timeline' or 'ledger'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff' }}>
      {/* Tab buttons */}
      <div style={{ display: 'flex', gap: '8px', padding: '12px 16px', borderBottom: '1px solid #e0e0e0' }}>
        <Button
          minimal
          small
          text="🔄 Flow Timeline"
          active={activeTab === 'timeline'}
          onClick={() => setActiveTab('timeline')}
        />
        <Button
          minimal
          small
          text="🔑 Receipt Ledger"
          active={activeTab === 'ledger'}
          onClick={() => setActiveTab('ledger')}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {activeTab === 'timeline' && <FlowTimeline />}
        {activeTab === 'ledger' && (
          <div style={{ padding: '16px', overflowY: 'auto', height: '100%' }}>
            <ReceiptLedger />
          </div>
        )}
      </div>
    </div>
  )
}

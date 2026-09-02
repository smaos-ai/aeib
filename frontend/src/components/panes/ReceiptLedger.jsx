import React, { useState } from 'react'
import { Card, Button, H5, Code, Tag, Tooltip, Intent } from '@blueprintjs/core'
import { verifyReceipt } from '../../lib/signing'
import { useGovernance } from '../../state/GovernanceContext'

export default function ReceiptLedger() {
  const { state } = useGovernance()
  const [expandedId, setExpandedId] = useState(null)
  const [verifyResults, setVerifyResults] = useState({})
  const [copiedText, setCopiedText] = useState(null)

  const handleVerify = async (receipt) => {
    const isValid = await verifyReceipt(receipt)
    setVerifyResults(prev => ({ ...prev, [receipt.id]: isValid }))
  }

  const handleCopy = (text, label) => {
    navigator.clipboard.writeText(text)
    setCopiedText(label)
    setTimeout(() => setCopiedText(null), 2000)
  }

  const actionIcon = (action) => {
    const actionStr = action || ''
    if (!actionStr) return '📝'
    if (actionStr.includes('authorize')) return '✅'
    if (actionStr.includes('revise')) return '🚫'
    if (actionStr.includes('submit')) return '📤'
    return '📝'
  }

  if (state.receipts.length === 0) {
    return (
      <Card style={{ background: '#f9fafb', padding: '12px', borderRadius: '4px' }}>
        <H5 style={{ margin: '0 0 8px 0', fontSize: '13px', fontWeight: '600', color: '#666' }}>
          📜 agentacct Proof Ledger
        </H5>
        <div style={{ fontSize: '12px', color: '#999999', marginTop: '8px' }}>
          ⏳ Awaiting first governance action. Submit an intent to begin recording the immutable audit trail.
        </div>
      </Card>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <H5 style={{ margin: '0', fontSize: '13px', fontWeight: '600', color: '#000000' }}>
          📜 agentacct Proof Ledger
        </H5>
        <Tag minimal intent={Intent.SUCCESS}>{state.receipts.length} entries</Tag>
      </div>

      {/* Public key display */}
      {state.receipts.length > 0 && (
        <Card style={{ background: '#f0f9ff', border: '1px solid #0066cc', padding: '10px', fontSize: '10px', borderRadius: '4px' }}>
          <div style={{ fontWeight: 'bold', color: '#0066cc', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            🔑 Session Public Key {state.receipts[0]?.alg === 'Ed25519' ? '(Post-Quantum)' : '(ECDSA P-256)'}
          </div>
          <Code style={{ wordBreak: 'break-all', fontSize: '9px', color: '#000000', display: 'block', marginBottom: '6px' }}>
            {state.receipts[0]?.publicKeyBase64?.slice(0, 60)}...
          </Code>
          <div style={{ fontSize: '9px', color: '#0066cc', cursor: 'pointer' }} onClick={() => handleCopy(state.receipts[0]?.publicKeyBase64, 'key')}>
            {copiedText === 'key' ? '✓ Copied' : '📋 Copy full key'}
          </div>
        </Card>
      )}

      {/* Timeline visualization */}
      {state.receipts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {state.receipts.map((receipt, idx) => {
            const isExpanded = expandedId === receipt.id
            const verifyStatus = verifyResults[receipt.id]
            const isLatest = idx === 0

            return (
              <Card
                key={receipt.id}
                style={{
                  background: isExpanded ? '#f8f9fa' : '#ffffff',
                  border: `2px solid ${verifyStatus === true ? '#00aa00' : verifyStatus === false ? '#dd0000' : isLatest ? '#0066cc' : '#cccccc'}`,
                  padding: '10px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  borderRadius: '4px',
                  animation: isLatest && !isExpanded ? 'slideIn 0.4s ease' : 'none'
                }}
                onClick={() => setExpandedId(isExpanded ? null : receipt.id)}
              >
                {/* Collapsed: Timeline entry */}
                {!isExpanded && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', color: '#000000' }}>
                    <div style={{ fontSize: '14px', minWidth: '20px' }}>
                      {actionIcon(receipt.action)}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: '600', fontSize: '12px' }}>
                        {receipt.timestamp?.slice(11, 19)} · {(receipt.action || receipt.payload?.action || 'unknown').toUpperCase().replace(/\./g, ' ')}
                      </div>
                      <div style={{ fontSize: '10px', color: '#666', marginTop: '2px' }}>
                        {receipt.alg} signature · {verifyStatus === true ? '✓ Verified' : verifyStatus === false ? '✗ Invalid' : '⏳ Unverified'}
                      </div>
                    </div>
                    <div style={{ fontSize: '14px', minWidth: '20px', textAlign: 'center' }}>
                      {isLatest && <span style={{ color: '#0066cc', fontWeight: 'bold' }}>←</span>}
                    </div>
                  </div>
                )}

                {/* Expanded: Full details */}
                {isExpanded && (
                  <div style={{ fontSize: '10px', color: '#000000', lineHeight: '1.6', animation: 'expandDown 0.2s ease' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                      <span style={{ fontSize: '16px' }}>{actionIcon(receipt.action)}</span>
                      <div>
                        <div style={{ fontWeight: 'bold', fontSize: '11px' }}>{(receipt.action || receipt.payload?.action || 'unknown').toUpperCase()}</div>
                        <div style={{ fontSize: '9px', color: '#666' }}>{receipt.timestamp}</div>
                      </div>
                      <div style={{ marginLeft: 'auto' }}>
                        <Tag intent={verifyStatus === true ? Intent.SUCCESS : verifyStatus === false ? Intent.DANGER : Intent.NONE}>
                          {verifyStatus === true ? '✓ VERIFIED' : verifyStatus === false ? '✗ INVALID' : '⏳ PENDING'}
                        </Tag>
                      </div>
                    </div>

                    {/* Metadata */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                      <div style={{ background: '#f5f5f5', padding: '6px', borderRadius: '3px' }}>
                        <div style={{ fontWeight: 'bold', color: '#0066cc', fontSize: '9px' }}>Algorithm</div>
                        <div style={{ marginTop: '2px', fontSize: '10px' }}>{receipt.alg}</div>
                      </div>
                      <div style={{ background: '#f5f5f5', padding: '6px', borderRadius: '3px' }}>
                        <div style={{ fontWeight: 'bold', color: '#0066cc', fontSize: '9px' }}>Receipt ID</div>
                        <div style={{ marginTop: '2px', fontSize: '9px', wordBreak: 'break-all' }}>{receipt.id?.slice(0, 20)}...</div>
                      </div>
                    </div>

                    {/* Payload */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontWeight: 'bold', color: '#0066cc', marginBottom: '4px', fontSize: '10px' }}>Canonical Payload</div>
                      <Code style={{ display: 'block', background: '#f9fafb', padding: '8px', fontSize: '9px', wordBreak: 'break-all', color: '#333333', maxHeight: '100px', overflowY: 'auto', borderRadius: '3px' }}>
                        {receipt.payloadCanonicalJSON}
                      </Code>
                      <Button
                        minimal
                        small
                        text={copiedText === 'payload' ? '✓ Copied' : '📋 Copy'}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleCopy(receipt.payloadCanonicalJSON, 'payload')
                        }}
                        style={{ marginTop: '4px', fontSize: '10px' }}
                      />
                    </div>

                    {/* Signature */}
                    <div style={{ marginBottom: '12px' }}>
                      <div style={{ fontWeight: 'bold', color: '#0066cc', marginBottom: '4px', fontSize: '10px' }}>Cryptographic Signature</div>
                      <Code style={{ display: 'block', background: '#f9fafb', padding: '8px', fontSize: '9px', wordBreak: 'break-all', color: '#333333', maxHeight: '80px', overflowY: 'auto', borderRadius: '3px' }}>
                        {receipt.signatureBase64}
                      </Code>
                      <Button
                        minimal
                        small
                        text={copiedText === 'sig' ? '✓ Copied' : '📋 Copy'}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleCopy(receipt.signatureBase64, 'sig')
                        }}
                        style={{ marginTop: '4px', fontSize: '10px' }}
                      />
                    </div>

                    {/* Verify button */}
                    <Tooltip content={verifyStatus === true ? 'Signature is cryptographically valid' : verifyStatus === false ? 'Signature verification failed' : 'Click to verify signature'}>
                      <Button
                        text={verifyStatus === true ? '✓ Signature Verified' : verifyStatus === false ? '✗ Signature Invalid' : 'Verify Signature (crypto.subtle.verify)'}
                        intent={verifyStatus === true ? 'success' : verifyStatus === false ? 'danger' : 'primary'}
                        small
                        onClick={(e) => {
                          e.stopPropagation()
                          handleVerify(receipt)
                        }}
                        style={{ width: '100%' }}
                      />
                    </Tooltip>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(-10px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes expandDown {
          from { max-height: 0; opacity: 0; }
          to { max-height: 500px; opacity: 1; }
        }
      `}</style>
    </div>
  )
}

import React from 'react'
import { Button, Card, H5 } from '@blueprintjs/core'
import { signPayload } from '../../../lib/signing'
import { useGovernance } from '../../../state/GovernanceContext'

export default function BaselIIIVetoCard({ onAuthorize, onRevise }) {
  const { addReceipt } = useGovernance()
  const [signing, setSigning] = React.useState(false)

  const handleAuthorize = async () => {
    setSigning(true)
    const receipt = await signPayload({
      action: 'veto.authorize',
      policy: 'BASEL_III_CAR_BUFFER',
      violationType: 'CET1_RATIO_BREACH',
      currentRatio: '10.18%',
      threshold: '10.50%',
      decision: 'AUTHORIZED_BY_CRO',
    })
    addReceipt(receipt)
    setSigning(false)
    onAuthorize?.(receipt)
  }

  const handleRevise = async () => {
    setSigning(true)
    const receipt = await signPayload({
      action: 'veto.revise',
      policy: 'BASEL_III_CAR_BUFFER',
      violationType: 'CET1_RATIO_BREACH',
      decision: 'VETOED_REQUIRES_REDESIGN',
    })
    addReceipt(receipt)
    setSigning(false)
    onRevise?.(receipt)
  }

  return (
    <Card style={{ background: '#fff5f0', border: '2px solid #ff8800', padding: '16px', marginTop: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '20px' }}>⚠️</span>
        <div>
          <H5 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: '700', color: '#ff8800' }}>
            EU AI Act Article 14 / Basel III Capital Adequacy Gate
          </H5>
          <div style={{ fontSize: '10px', color: '#ff8800', fontWeight: 'bold' }}>EXECUTION SUSPENDED (&lt;0.08ms)</div>
        </div>
      </div>

      <div style={{ background: '#fafafa', border: '1px solid #ff8800', borderRadius: '6px', padding: '12px', marginBottom: '12px', fontSize: '11px', fontFamily: 'monospace', color: '#333333', lineHeight: '1.6' }}>
        <div><strong>TRIGGER POLICY:</strong> CRR-BASEL-III-CAPITAL-BUFFER</div>
        <div><strong>AGENT INTENT:</strong> Automatic loan portfolio rebalancing (RWA adjustment)</div>
        <div><strong>PROJECTED CET1 RATIO:</strong> <span style={{ color: '#dd0000', fontWeight: 'bold' }}>10.18% (Regulatory Floor: 10.50%)</span></div>
        <div><strong>VIOLATION:</strong> Capital buffer breach — <span style={{ color: '#dd0000' }}>€32M shortfall</span></div>
        <div><strong>LEGAL BASIS:</strong> Basel III, CRD V, Article 92 CRR (minimum capital requirements)</div>
      </div>

      <div style={{ background: '#fff9e6', borderLeft: '4px solid #ff8800', padding: '10px', marginBottom: '12px', fontSize: '11px', color: '#333333', lineHeight: '1.5' }}>
        <strong>This action requires mandatory human authorization and cryptographic Ed25519 countersigning before execution. The CRO's digital signature is legally non-repudiable and auditable.</strong>
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <Button
          text={signing ? 'Signing...' : 'Authorize & Sign (Ed25519)'}
          intent="success"
          onClick={handleAuthorize}
          disabled={signing}
          style={{ flex: 1 }}
        />
        <Button
          text="Veto & Abort"
          intent="warning"
          onClick={handleRevise}
          disabled={signing}
          style={{ flex: 1 }}
        />
      </div>

      {signing && (
        <div style={{ fontSize: '10px', color: '#00aa00', marginTop: '8px', textAlign: 'center', fontWeight: 'bold' }}>
          ⏳ Generating Ed25519 signature...
        </div>
      )}
    </Card>
  )
}
